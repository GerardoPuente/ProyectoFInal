"""API de ClipShare: registro, login, subida de clips a S3 y consulta."""
import re
import uuid
from contextlib import asynccontextmanager

import psycopg
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from clipshare import db, reglas, seguridad, storage
from clipshare.config import Config

cfg = Config()
s3 = storage.cliente_s3(cfg)


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    db.crear_esquema(cfg)
    yield


app = FastAPI(title="ClipShare", lifespan=ciclo_de_vida)
app.mount("/static", StaticFiles(directory="/app/api/static"), name="static")

PATRON_USUARIO = re.compile(r"^[a-zA-Z0-9_]{3,30}$")


class Credenciales(BaseModel):
    usuario: str
    password: str


def usuario_actual(authorization: str = Header(default="")) -> int:
    token = authorization.removeprefix("Bearer ").strip()
    uid = seguridad.leer_token(cfg.secret_key, token, cfg.token_horas) if token else None
    if uid is None:
        raise HTTPException(status_code=401, detail="Sesion invalida o expirada")
    return uid


@app.get("/")
def inicio():
    return FileResponse("/app/api/static/index.html")


@app.get("/salud")
def salud():
    """Vivo si la API responde y la base de datos contesta."""
    try:
        with db.conectar(cfg) as conn:
            conn.execute("SELECT 1")
    except psycopg.Error:
        return JSONResponse({"estado": "degradado", "base_de_datos": "sin conexion"}, status_code=503)
    return {"estado": "ok", "base_de_datos": "ok"}


@app.post("/registro", status_code=201)
def registro(c: Credenciales):
    if not PATRON_USUARIO.match(c.usuario):
        raise HTTPException(400, "Usuario: 3 a 30 caracteres (letras, numeros o _)")
    if len(c.password) < 8:
        raise HTTPException(400, "La contrasena debe tener al menos 8 caracteres")
    try:
        with db.conectar(cfg) as conn:
            fila = conn.execute(
                "INSERT INTO usuarios (usuario, password_hash) VALUES (%s, %s) RETURNING id",
                (c.usuario, seguridad.hashear_password(c.password)),
            ).fetchone()
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "Ese usuario ya existe")
    return {"id": fila["id"], "usuario": c.usuario}


@app.post("/login")
def login(c: Credenciales):
    with db.conectar(cfg) as conn:
        fila = conn.execute(
            "SELECT id, password_hash FROM usuarios WHERE usuario = %s", (c.usuario,)
        ).fetchone()
    if not fila or not seguridad.verificar_password(c.password, fila["password_hash"]):
        raise HTTPException(401, "Usuario o contrasena incorrectos")
    return {"token": seguridad.crear_token(cfg.secret_key, fila["id"]), "usuario": c.usuario}


@app.post("/clips", status_code=202)
def subir_clip(
    titulo: str = Form(..., max_length=120),
    archivo: UploadFile = File(...),
    uid: int = Depends(usuario_actual),
):
    """Guarda el clip en S3 y lo deja 'pendiente'; el worker lo procesa aparte."""
    if not reglas.extension_valida(archivo.filename) or not reglas.tipo_valido(archivo.content_type):
        raise HTTPException(415, "Formato no permitido (mp4, mov, webm o mkv)")

    # Se mide el tamano real del flujo, sin confiar en el encabezado del cliente
    archivo.file.seek(0, 2)
    tamano = archivo.file.tell()
    archivo.file.seek(0)
    if tamano == 0:
        raise HTTPException(400, "El archivo esta vacio")
    if tamano > cfg.max_bytes:
        raise HTTPException(413, f"El clip supera el maximo de {cfg.max_bytes // (1024 * 1024)} MB")

    clip_id = uuid.uuid4()
    nombre = reglas.nombre_seguro(archivo.filename)
    extension = nombre[nombre.rfind("."):].lower()
    clave = f"clips/{uid}/{clip_id}/original{extension}"
    s3.upload_fileobj(archivo.file, cfg.s3_bucket, clave, ExtraArgs={"ContentType": archivo.content_type})
    with db.conectar(cfg) as conn:
        conn.execute(
            "INSERT INTO clips (id, usuario_id, titulo, nombre_original, clave_s3, bytes) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (clip_id, uid, titulo.strip() or nombre, nombre, clave, tamano),
        )
    return {"id": str(clip_id), "estado": "pendiente"}


CONSULTA = "SELECT c.*, u.usuario AS autor FROM clips c JOIN usuarios u ON u.id = c.usuario_id "


def _serializar(f: dict) -> dict:
    miniatura = storage.url_firmada(s3, cfg, f["clave_miniatura"]) if f["clave_miniatura"] else None
    return {
        "id": str(f["id"]),
        "titulo": f["titulo"],
        "autor": f["autor"],
        "estado": f["estado"],
        "duracion_s": f["duracion_s"],
        "resolucion": f"{f['ancho']}x{f['alto']}" if f["ancho"] else None,
        "codec": f["codec"],
        "motivo_rechazo": f["motivo_rechazo"] if f["estado"] == "rechazado" else None,
        "miniatura": miniatura,
        "creado_en": f["creado_en"].isoformat(),
    }


@app.get("/clips")
def listar_clips(uid: int = Depends(usuario_actual)):
    """Clips ya procesados de todos, mas los propios aunque sigan en proceso o rechazados."""
    with db.conectar(cfg) as conn:
        filas = conn.execute(
            CONSULTA + "WHERE c.estado = 'listo' OR c.usuario_id = %s ORDER BY c.creado_en DESC LIMIT 100",
            (uid,),
        ).fetchall()
    return [_serializar(f) for f in filas]


@app.get("/clips/{clip_id}")
def ver_clip(clip_id: uuid.UUID, uid: int = Depends(usuario_actual)):
    with db.conectar(cfg) as conn:
        f = conn.execute(CONSULTA + "WHERE c.id = %s", (clip_id,)).fetchone()
    if not f or (f["estado"] != "listo" and f["usuario_id"] != uid):
        raise HTTPException(404, "Clip no encontrado")
    datos = _serializar(f)
    datos["video"] = storage.url_firmada(s3, cfg, f["clave_s3"]) if f["estado"] == "listo" else None
    return datos
