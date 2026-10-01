"""Politica de Dockerfile endurecido: version fija, sin root, HEALTHCHECK, sin secretos.

Uso: python politica_dockerfile.py Dockerfile.api Dockerfile.worker
Sale con codigo 1 si cualquier Dockerfile incumple alguna regla.
"""
import re
import sys

PATRON_SECRETO = re.compile(r"\b\w*(PASSWORD|SECRET|TOKEN|API_?KEY|ACCESS_?KEY)\w*\s*=\s*\S+", re.I)


def revisar(ruta: str) -> list[str]:
    with open(ruta, encoding="utf-8") as f:
        lineas = [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]
    fallos = []

    imagenes = [l.split()[1] for l in lineas if l.upper().startswith("FROM ")]
    for img in imagenes:
        if img.lower() == "scratch":
            continue
        if "@sha256:" in img:
            continue
        etiqueta = img.split(":", 1)[1] if ":" in img else ""
        if not etiqueta or etiqueta == "latest":
            fallos.append(f"FROM {img}: la imagen base no tiene version fija")

    usuarios = [l.split()[1] for l in lineas if l.upper().startswith("USER ")]
    if not usuarios:
        fallos.append("no define USER: el proceso corre como root")
    elif usuarios[-1].split(":")[0] in ("root", "0"):
        fallos.append("el USER final es root")

    if not any(l.upper().startswith("HEALTHCHECK ") for l in lineas):
        fallos.append("no define HEALTHCHECK")

    for l in lineas:
        if l.upper().startswith(("ENV ", "ARG ")) and PATRON_SECRETO.search(l):
            fallos.append(f"posible secreto dentro del Dockerfile: {l.split('=')[0]}=***")

    return fallos


if __name__ == "__main__":
    total = 0
    for ruta in sys.argv[1:]:
        fallos = revisar(ruta)
        total += len(fallos)
        print(f"{ruta}: {'CUMPLE' if not fallos else 'INCUMPLE'}")
        for f in fallos:
            print(f"   - {f}")
    sys.exit(1 if total else 0)
