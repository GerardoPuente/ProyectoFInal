"""
PARCHE - Nueva funcionalidad: exportar clip en resolucion reducida
Tema: Clips cortos

Producto pide: el usuario puede pedir una version en baja resolucion de su
clip ya subido, para compartirla mas rapido en redes con poco ancho de banda.

Codigo entregado por el docente (exportar_clip.py, Flask) traducido a FastAPI.
Las lineas marcadas ADAPTACION son lo unico que cambie para que funcione con
mi almacenamiento (los clips estan en S3, no en /data/clips).
"""
import os
import subprocess
import uuid

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import FileResponse

from clipshare import db, storage
from clipshare.config import Config

exportar_router = APIRouter()

CARPETA_CLIPS = "/tmp/clips"  # ADAPTACION: tmpfs del contenedor (era /data/clips)
CARPETA_EXPORTS = "/tmp/exports"  # ADAPTACION: tmpfs del contenedor (era /data/exports)

cfg = Config()
s3 = storage.cliente_s3(cfg)


def _traer_clip_de_s3(clip_id: str, origen: str) -> None:
    """ADAPTACION: baja el clip de S3 a CARPETA_CLIPS para que el resto del codigo sea el original."""
    try:
        identificador = uuid.UUID(clip_id)
    except ValueError:
        return
    with db.conectar(cfg) as conn:
        fila = conn.execute("SELECT clave_s3 FROM clips WHERE id = %s", (identificador,)).fetchone()
    if fila:
        os.makedirs(CARPETA_CLIPS, exist_ok=True)
        os.makedirs(CARPETA_EXPORTS, exist_ok=True)
        s3.download_file(cfg.s3_bucket, fila["clave_s3"], origen)


@exportar_router.post("/clips/{clip_id}/exportar")
def exportar_clip_baja_resolucion(clip_id: str, datos: dict = Body(default={})):
    """Genera una copia en baja resolucion del clip usando ffmpeg."""
    resolucion = datos.get("resolucion", "480x270")
    origen = os.path.join(CARPETA_CLIPS, f"{clip_id}.mp4")
    destino = os.path.join(CARPETA_EXPORTS, f"{clip_id}_{resolucion}.mp4")

    _traer_clip_de_s3(clip_id, origen)  # ADAPTACION

    if not os.path.isfile(origen):
        raise HTTPException(status_code=404, detail="clip no encontrado")

    comando = f"ffmpeg -y -i {origen} -vf scale={resolucion} {destino}"
    subprocess.call(comando, shell=True)

    return FileResponse(destino, media_type="video/mp4")
