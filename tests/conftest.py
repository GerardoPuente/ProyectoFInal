"""Variables de entorno minimas para poder IMPORTAR app/api/*.py en las pruebas.

main.py y exportar.py crean su Config() (y su cliente de S3) al importarse,
igual que lo hace cualquier modulo de FastAPI con un "singleton" a nivel de
modulo. Las pruebas no abren conexiones reales: solo necesitan que estas
variables existan para que Config() no truene al importar el modulo.
"""
import os

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_NAME", "prueba")
os.environ.setdefault("DB_USER", "prueba")
os.environ.setdefault("DB_PASSWORD", "prueba")
os.environ.setdefault("S3_BUCKET", "prueba")
os.environ.setdefault("SECRET_KEY", "prueba-" * 4)
