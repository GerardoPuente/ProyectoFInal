"""
Exportar clip en resolucion reducida (tema 1: clips cortos).

Producto pide: el usuario puede pedir una version en baja resolucion de su
clip ya subido, para compartirla mas rapido en redes con poco ancho de banda.

REMEDIADO: version original entregada por el docente documentada en
docs/clasificacion_hallazgo.md (CWE-78, inyeccion de comandos) y
docs/respuesta_incidente.md. Causa raiz corregida:
`subprocess.call(f"...{resolucion}...", shell=True)` con texto del cliente
concatenado -> `subprocess.run([...], shell=False)` con una lista fija de
argumentos y la resolucion restringida a una lista blanca. Ademas se agrego
autenticacion y verificacion de dueno (el endpoint original no tenia ninguna
de las dos).
"""
import os
import subprocess
import tempfile
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import FileResponse

from clipshare import db, storage
from clipshare.auth import dependencia_usuario_actual
from clipshare.config import Config

exportar_router = APIRouter()

# Lista blanca: solo estas resoluciones se aceptan. Cierra la inyeccion de raiz
# (no hay texto del cliente que llegue al comando) y de paso evita que alguien
# pida una escala absurda que agote CPU/memoria del contenedor.
RESOLUCIONES_PERMITIDAS = {"640x360", "480x270", "320x180"}

cfg = Config()
s3 = storage.cliente_s3(cfg)
usuario_actual = dependencia_usuario_actual(cfg)


@exportar_router.post("/clips/{clip_id}/exportar")
def exportar_clip_baja_resolucion(
    clip_id: uuid.UUID,
    datos: dict = Body(default={}),
    uid: int = Depends(usuario_actual),
):
    """Genera, en el momento, una copia en baja resolucion del clip y la entrega."""
    resolucion = datos.get("resolucion", "480x270")
    if resolucion not in RESOLUCIONES_PERMITIDAS:
        raise HTTPException(
            status_code=400,
            detail=f"Resolucion no permitida. Usa una de: {sorted(RESOLUCIONES_PERMITIDAS)}",
        )

    with db.conectar(cfg) as conn:
        fila = conn.execute(
            "SELECT clave_s3, usuario_id, estado FROM clips WHERE id = %s", (clip_id,)
        ).fetchone()
    if not fila:
        raise HTTPException(status_code=404, detail="clip no encontrado")
    if fila["usuario_id"] != uid:
        # Mismo criterio de propiedad que ya usa GET /clips/{id}: solo el dueno exporta su clip.
        raise HTTPException(status_code=404, detail="clip no encontrado")
    if fila["estado"] != "listo":
        raise HTTPException(status_code=409, detail="el clip todavia no esta listo")

    with tempfile.TemporaryDirectory() as tmp:
        origen = os.path.join(tmp, "original.mp4")
        destino = os.path.join(tmp, f"export_{resolucion}.mp4")
        s3.download_file(cfg.s3_bucket, fila["clave_s3"], origen)

        # subprocess.run con una LISTA de argumentos y shell=False (por defecto):
        # no hay shell que interprete ";", "&&", "|" ni nada mas. "scale=..." ya
        # no lleva texto del cliente sin filtrar, porque "resolucion" salio de
        # la lista blanca de arriba.
        resultado = subprocess.run(
            ["ffmpeg", "-y", "-i", origen, "-vf", f"scale={resolucion}", destino],
            capture_output=True, timeout=60, check=False,
        )
        if resultado.returncode != 0 or not os.path.exists(destino):
            raise HTTPException(status_code=500, detail="no se pudo generar la exportacion")

        # FileResponse necesita que el archivo exista cuando Starlette lo envia;
        # se copia fuera del directorio temporal antes de que este se borre.
        salida_final = os.path.join(tempfile.gettempdir(), f"export_{clip_id}_{resolucion}.mp4")
        with open(destino, "rb") as f_in, open(salida_final, "wb") as f_out:
            f_out.write(f_in.read())

    return FileResponse(salida_final, media_type="video/mp4", filename=f"{clip_id}_{resolucion}.mp4")
