"""Reglas de validacion de clips. Sin dependencias externas para poder probarlas."""
import os

EXTENSIONES_PERMITIDAS = {".mp4", ".mov", ".webm", ".mkv"}
TIPOS_PERMITIDOS = {"video/mp4", "video/quicktime", "video/webm", "video/x-matroska"}


def extension_valida(nombre: str) -> bool:
    return os.path.splitext(nombre or "")[1].lower() in EXTENSIONES_PERMITIDAS


def tipo_valido(content_type: str) -> bool:
    return (content_type or "").split(";")[0].strip().lower() in TIPOS_PERMITIDOS


def nombre_seguro(nombre: str) -> str:
    """Solo se conserva el nombre base, sin rutas ni caracteres raros."""
    base = os.path.basename((nombre or "clip").replace("\\", "/"))
    limpio = "".join(c if c.isalnum() or c in "._- " else "_" for c in base)
    return limpio[:120] or "clip"


def validar_resultado_ffprobe(info: dict, max_duracion_s: int) -> tuple[bool, str]:
    """Decide si lo que ffprobe leyo es un video aceptable. Devuelve (ok, motivo)."""
    streams = info.get("streams", [])
    if not any(s.get("codec_type") == "video" for s in streams):
        return False, "El archivo no contiene una pista de video"
    try:
        duracion = float(info.get("format", {}).get("duration", 0))
    except (TypeError, ValueError):
        return False, "No se pudo leer la duracion"
    if duracion <= 0:
        return False, "Duracion invalida"
    if duracion > max_duracion_s:
        return False, f"Dura {duracion:.0f}s y el maximo es {max_duracion_s}s"
    return True, ""
