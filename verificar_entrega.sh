#!/bin/bash
# Verificador de la ENTREGA del Avance 2 del Reto - LSCA2314
#
# No revisa la calidad de tu aplicacion (eso lo califica el docente con la
# rubrica). Revisa que tu entrega este COMPLETA: que existan las piezas
# obligatorias, que no hayas dejado plantillas sin llenar y que tengas la
# evidencia de tu pipeline en rojo y en verde.
#
# Correlo desde la raiz de tu repositorio antes de entregar.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR" || exit 1

TOTAL=0
OK=0

check() {
  TOTAL=$((TOTAL+1))
  if eval "$2"; then
    echo "  [OK] $1"
    OK=$((OK+1))
  else
    echo "  [ ] $1"
  fi
}

echo "=================================================="
echo " Verificacion de entrega - Avance 2 del Reto"
echo "=================================================="

echo ""
echo "--- Aplicacion ---"
check "Hay codigo de aplicacion en app/" \
  "[ -n \"\$(find app -type f ! -name '.gitkeep' 2>/dev/null)\" ]"
check "Existe docker-compose.yml (o compose.yaml)" \
  "[ -f docker-compose.yml ] || [ -f docker-compose.yaml ] || [ -f compose.yaml ]"

COMPOSE=""
for f in docker-compose.yml docker-compose.yaml compose.yaml; do
  [ -f "$f" ] && COMPOSE="$f" && break
done

SERVICIOS=0
if [ -n "$COMPOSE" ]; then
  SERVICIOS=$(awk '
    /^services:/ {dentro=1; next}
    /^[a-zA-Z_-]+:/ {dentro=0}
    dentro && /^  [a-zA-Z0-9_-]+:/ {n++}
    END {print n+0}
  ' "$COMPOSE")
fi
check "El compose define al menos 2 servicios (encontrados: $SERVICIOS)" \
  "[ \"$SERVICIOS\" -ge 2 ]"

check "Existe al menos un Dockerfile" \
  "[ -n \"\$(find . -name 'Dockerfile*' -not -path './venv/*' 2>/dev/null)\" ]"
check "Existe un endpoint /salud en el codigo" \
  "grep -rq '/salud' app/ 2>/dev/null"

echo ""
echo "--- Infraestructura como codigo ---"
check "Hay al menos un archivo .tf en infra/" \
  "[ -n \"\$(find infra -name '*.tf' 2>/dev/null)\" ]"
check "El IaC menciona el bucket de S3" \
  "grep -rqi 's3' infra/ 2>/dev/null"
check "El IaC menciona la base de datos (RDS)" \
  "grep -rqi 'db_instance\|rds' infra/ 2>/dev/null"

echo ""
echo "--- Pipeline propio ---"
check "Hay archivos de pipeline en pipeline/" \
  "[ -n \"\$(find pipeline -type f ! -name '.gitkeep' 2>/dev/null)\" ]"
check "Evidencia de la corrida en ROJO (reportes/corrida_roja.txt)" \
  "[ -s reportes/corrida_roja.txt ]"
check "La corrida roja efectivamente bloquea" \
  "grep -qi 'bloquead' reportes/corrida_roja.txt 2>/dev/null"
check "Evidencia de la corrida en VERDE (reportes/corrida_verde.txt)" \
  "[ -s reportes/corrida_verde.txt ]"
check "La corrida verde efectivamente permite" \
  "grep -qi 'permitid' reportes/corrida_verde.txt 2>/dev/null"

echo ""
echo "--- SBOM ---"
SBOM="$(find . -name 'sbom*.json' -not -path './venv/*' 2>/dev/null | head -1)"
check "Existe un archivo de SBOM" "[ -n \"$SBOM\" ]"
if [ -n "$SBOM" ]; then
  check "El SBOM es CycloneDX valido" \
    "python3 -c \"import json,sys;d=json.load(open('$SBOM'));sys.exit(0 if d.get('bomFormat')=='CycloneDX' else 1)\" 2>/dev/null"
fi

echo ""
echo "--- Documentacion ---"
check "docs/README.md existe" "[ -f docs/README.md ]"
check "docs/ADR-001-decisiones-tecnicas.md existe" "[ -f docs/ADR-001-decisiones-tecnicas.md ]"
check "docs/tabla_decisiones_pipeline.md existe" "[ -f docs/tabla_decisiones_pipeline.md ]"
check "docs/declaracion_uso_ia.md existe" "[ -f docs/declaracion_uso_ia.md ]"
check "Hay un diagrama de arquitectura en docs/" \
  "[ -n \"\$(find docs -iname 'diagrama*' \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.svg' -o -iname '*.pdf' \) 2>/dev/null)\" ]"

PENDIENTES=$(grep -rl '\[COMPLETAR\]' docs/ 2>/dev/null | wc -l)
check "Ningun documento quedo con [COMPLETAR] (archivos pendientes: $PENDIENTES)" \
  "[ \"$PENDIENTES\" -eq 0 ]"

echo ""
echo "--- Video ---"
check "Hay video en video/ o el enlace en docs/enlace_video.txt" \
  "[ -n \"\$(find video -type f ! -name '.gitkeep' 2>/dev/null)\" ] || { [ -f docs/enlace_video.txt ] && ! grep -q '\[COMPLETAR\]' docs/enlace_video.txt; }"

echo ""
echo "--- Higiene del repositorio ---"
check "El archivo .env NO esta en el repositorio" "[ ! -f .env ]"
check ".gitignore protege el .env" "grep -q '^\.env' .gitignore 2>/dev/null"
check "No hay carpeta venv/ subida al repositorio" "[ ! -d venv ]"

echo ""
echo "=================================================="
echo " Resultado: $OK / $TOTAL"
echo "=================================================="

if [ "$OK" -eq "$TOTAL" ]; then
  echo "Tu entrega esta completa. Recuerda que esto NO califica la calidad"
  echo "de tu aplicacion ni de tus justificaciones: eso lo revisa el docente"
  echo "con la rubrica. Sube el enlace de tu repositorio y el documento de"
  echo "evidencias a la plataforma."
  exit 0
else
  echo "Faltan piezas de la entrega. Revisa la lista de arriba."
  exit 1
fi
