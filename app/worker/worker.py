"""Worker asincrono: toma clips 'pendiente', los valida con ffprobe, genera la
miniatura con ffmpeg y registra la duracion. Corre en su propio contenedor."""
import json
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path

from clipshare import db, reglas, storage
from clipshare.config import Config

logging.basicConfig(level=logging.INFO, format="%(asctime)s worker %(levelname)s %(message)s")
log = logging.getLogger("worker")

LATIDO = Path("/tmp/worker.latido")  # lo lee el HEALTHCHECK del contenedor
INTERVALO_S = 3


def reclamar(conn):
    """Toma un clip pendiente. SKIP LOCKED permite correr varios workers sin pisarse."""
    with conn.transaction():
        fila = conn.execute(
            "SELECT id, clave_s3 FROM clips WHERE estado = 'pendiente' "
            "ORDER BY creado_en LIMIT 1 FOR UPDATE SKIP LOCKED"
        ).fetchone()
        if fila:
            conn.execute("UPDATE clips SET estado = 'procesando' WHERE id = %s", (fila["id"],))
        return fila


def ffprobe(ruta: str) -> dict:
    salida = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", ruta],
        capture_output=True, text=True, timeout=60, check=False,
    )
    if salida.returncode != 0:
        return {}
    return json.loads(salida.stdout or "{}")


def miniatura(ruta_video: str, ruta_salida: str, duracion: float) -> bool:
    instante = min(1.0, duracion / 2)
    r = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", f"{instante:.2f}", "-i", ruta_video,
         "-frames:v", "1", "-vf", "scale=360:-2", ruta_salida],
        capture_output=True, timeout=60, check=False,
    )
    return r.returncode == 0 and os.path.exists(ruta_salida)


def procesar(cfg: Config, s3, conn, clip) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        origen = os.path.join(tmp, "original")
        s3.download_file(cfg.s3_bucket, clip["clave_s3"], origen)
        info = ffprobe(origen)
        ok, motivo = reglas.validar_resultado_ffprobe(info, cfg.max_duracion_s)
        if not ok:
            conn.execute(
                "UPDATE clips SET estado='rechazado', motivo_rechazo=%s, procesado_en=now() WHERE id=%s",
                (motivo or "No es un video valido", clip["id"]),
            )
            log.warning("Clip %s rechazado: %s", clip["id"], motivo)
            return
        duracion = float(info["format"]["duration"])
        video = next(s for s in info["streams"] if s.get("codec_type") == "video")
        clave_mini = None
        salida = os.path.join(tmp, "miniatura.jpg")
        if miniatura(origen, salida, duracion):
            clave_mini = clip["clave_s3"].rsplit("/", 1)[0] + "/miniatura.jpg"
            s3.upload_file(salida, cfg.s3_bucket, clave_mini, ExtraArgs={"ContentType": "image/jpeg"})
        conn.execute(
            "UPDATE clips SET estado='listo', duracion_s=%s, ancho=%s, alto=%s, codec=%s, "
            "clave_miniatura=%s, procesado_en=now() WHERE id=%s",
            (duracion, video.get("width"), video.get("height"), video.get("codec_name"), clave_mini, clip["id"]),
        )
        log.info("Clip %s listo: %.1fs %sx%s", clip["id"], duracion, video.get("width"), video.get("height"))


def main() -> None:
    cfg = Config()
    s3 = storage.cliente_s3(cfg)
    log.info("Worker iniciado, bucket=%s", cfg.s3_bucket)
    while True:
        LATIDO.touch()
        try:
            with db.conectar(cfg) as conn:
                clip = reclamar(conn)
                if clip is None:
                    time.sleep(INTERVALO_S)
                    continue
                try:
                    procesar(cfg, s3, conn, clip)
                except Exception as exc:  # un clip malo no debe tumbar al worker
                    log.exception("Fallo procesando %s", clip["id"])
                    conn.execute(
                        "UPDATE clips SET estado='rechazado', motivo_rechazo=%s, procesado_en=now() WHERE id=%s",
                        (f"Error de procesamiento: {type(exc).__name__}", clip["id"]),
                    )
        except Exception:
            log.exception("Sin conexion con la base de datos, reintentando")
            time.sleep(INTERVALO_S)


if __name__ == "__main__":
    main()
