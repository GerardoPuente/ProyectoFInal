#!/usr/bin/env bash
# Demostracion para el video: planta una llave de AWS FALSA en el codigo, corre
# el pipeline (debe BLOQUEAR) y limpia el archivo al terminar.
#   ./pipeline/demo_rojo.sh
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
ARCHIVO="app/clipshare/config_temporal.py"
trap 'rm -f "$ARCHIVO"; echo; echo "(archivo de prueba eliminado: $ARCHIVO)"' EXIT
LLAVE="AKIA$(LC_ALL=C tr -dc 'A-Z2-7' </dev/urandom | head -c 16)"
SECRETA="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 40)"
printf '# Prueba: credencial FALSA incrustada en el codigo\nAWS_ACCESS_KEY_ID = "%s"\nAWS_SECRET_ACCESS_KEY = "%s"\n' "$LLAVE" "$SECRETA" > "$ARCHIVO"
echo ">>> Se agrego $ARCHIVO con una credencial falsa. Corriendo el pipeline..."
./pipeline/run_pipeline.sh
