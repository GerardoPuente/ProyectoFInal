import boto3
from botocore.config import Config as BotoConfig

from .config import Config


def cliente_s3(cfg: Config):
    # Las credenciales salen de la cadena por defecto de boto3: en EC2 es el rol
    # de la instancia, asi que no hay llaves en el codigo ni en el .env.
    return boto3.client(
        "s3",
        region_name=cfg.aws_region,
        config=BotoConfig(signature_version="s3v4"),
    )


def url_firmada(s3, cfg: Config, clave: str, segundos: int = 900) -> str:
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": cfg.s3_bucket, "Key": clave},
        ExpiresIn=segundos,
    )
