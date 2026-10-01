import psycopg
from psycopg.rows import dict_row

from .config import Config

ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id            SERIAL PRIMARY KEY,
    usuario       TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    creado_en     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS clips (
    id               UUID PRIMARY KEY,
    usuario_id       INTEGER NOT NULL REFERENCES usuarios(id),
    titulo           TEXT NOT NULL,
    nombre_original  TEXT NOT NULL,
    clave_s3         TEXT NOT NULL,
    clave_miniatura  TEXT,
    estado           TEXT NOT NULL DEFAULT 'pendiente',
    duracion_s       DOUBLE PRECISION,
    ancho            INTEGER,
    alto             INTEGER,
    codec            TEXT,
    bytes            BIGINT,
    motivo_rechazo   TEXT,
    creado_en        TIMESTAMPTZ NOT NULL DEFAULT now(),
    procesado_en     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_clips_estado ON clips(estado, creado_en);
"""


def conectar(cfg: Config) -> psycopg.Connection:
    return psycopg.connect(
        host=cfg.db_host,
        port=cfg.db_port,
        dbname=cfg.db_name,
        user=cfg.db_user,
        password=cfg.db_password,
        row_factory=dict_row,
        connect_timeout=10,
    )


def crear_esquema(cfg: Config) -> None:
    with conectar(cfg) as conn:
        conn.execute(ESQUEMA)
