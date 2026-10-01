"""Dependencia de autenticacion compartida entre routers (api.main y api.exportar)
para no duplicarla ni crear un import circular entre ambos modulos."""
from fastapi import Header, HTTPException

from . import seguridad
from .config import Config


def dependencia_usuario_actual(cfg: Config):
    """Devuelve una dependencia de FastAPI ligada a la config de la app."""

    def usuario_actual(authorization: str = Header(default="")) -> int:
        token = authorization.removeprefix("Bearer ").strip()
        uid = seguridad.leer_token(cfg.secret_key, token, cfg.token_horas) if token else None
        if uid is None:
            raise HTTPException(status_code=401, detail="Sesion invalida o expirada")
        return uid

    return usuario_actual
