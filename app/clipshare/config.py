"""Configuracion: todo viene de variables de entorno, nada esta escrito en el codigo."""
import os


def _requerida(nombre: str) -> str:
    valor = os.environ.get(nombre)
    if not valor:
        raise RuntimeError(f"Falta la variable de entorno {nombre}")
    return valor


class Config:
    def __init__(self) -> None:
        self.db_host = _requerida("DB_HOST")
        self.db_port = int(os.environ.get("DB_PORT", "5432"))
        self.db_name = _requerida("DB_NAME")
        self.db_user = _requerida("DB_USER")
        self.db_password = _requerida("DB_PASSWORD")
        self.s3_bucket = _requerida("S3_BUCKET")
        self.aws_region = os.environ.get("AWS_REGION", "us-east-1")
        self.secret_key = _requerida("SECRET_KEY")
        # Limites de subida: el clip es "de pocos minutos"
        self.max_bytes = int(os.environ.get("MAX_UPLOAD_MB", "50")) * 1024 * 1024
        self.max_duracion_s = int(os.environ.get("MAX_DURACION_S", "300"))
        self.token_horas = int(os.environ.get("TOKEN_HORAS", "12"))
        # Bandera de contencion inmediata (docs/respuesta_incidente.md): permite
        # apagar el endpoint de exportar sin tocar codigo ni redesplegar nada.
        self.exportar_habilitado = os.environ.get("EXPORTAR_CLIPS_HABILITADO", "true").lower() == "true"
