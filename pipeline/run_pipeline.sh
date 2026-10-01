#!/usr/bin/env bash
# Pipeline de seguridad y calidad de ClipShare.
#
# Uso:  ./pipeline/run_pipeline.sh [archivo_de_salida]
#   p.ej. ./pipeline/run_pipeline.sh reportes/corrida_roja.txt
#
# Corre TODAS las etapas (para ver todos los hallazgos de una vez) y al final
# emite UN solo veredicto: DESPLIEGUE BLOQUEADO (exit 1) o PERMITIDO (exit 0).
# Los umbrales y su justificacion estan en docs/tabla_decisiones_pipeline.md.

cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
RAIZ="$(pwd)"
SALIDA="${1:-}"
if [ -n "$SALIDA" ] && [ -z "${PIPELINE_TEE:-}" ]; then
  mkdir -p "$(dirname "$SALIDA")"
  PIPELINE_TEE=1 bash "$0" 2>&1 | sed -u -e 's/\x1b\[[0-9;]*[A-Za-z]//g' -e 's/\r/\n/g' | tee "$SALIDA"
  exit "${PIPESTATUS[0]}"
fi

# ----- versiones fijas de las herramientas (reproducibles) -----
IMG_TRIVY="aquasec/trivy:0.74.0"
IMG_GITLEAKS="zricethezav/gitleaks:v8.30.1"
UMBRAL_SEV="HIGH,CRITICAL"

TMP="$RAIZ/.pipeline-tmp"
FUENTE="$TMP/fuente"
rm -rf "$TMP" && mkdir -p "$FUENTE"

# Ruta que Docker entiende (en Git Bash de Windows hay que usar el formato C:/...)
ruta_docker() { (cd "$1" && (pwd -W 2>/dev/null || pwd)); }
DOCKER_TMP="$(ruta_docker "$TMP")"

dk() { MSYS_NO_PATHCONV=1 docker run --rm "$@"; }
trivy() { dk -v "$DOCKER_TMP:/work" -v trivy-cache:/root/.cache -w /work "$IMG_TRIVY" "$@"; }

RESULTADOS=()
etapa() {  # etapa "Nombre" "umbral que bloquea" comando...
  local nombre="$1" umbral="$2"; shift 2
  echo
  echo "=================================================================="
  echo " ETAPA: $nombre"
  echo " Umbral que bloquea: $umbral"
  echo "=================================================================="
  if "$@"; then
    echo "--> [APROBADA] $nombre"
    RESULTADOS+=("OK|$nombre|$umbral")
  else
    echo "--> [FALLO] $nombre"
    RESULTADOS+=("FALLO|$nombre|$umbral")
  fi
}

echo "Pipeline ClipShare - $(date '+%Y-%m-%d %H:%M:%S')"
echo "Commit: $(git rev-parse --short HEAD 2>/dev/null || echo 'sin commits aun')"

# ----- Fuente a analizar: lo que git subiria (respeta .gitignore, incluye lo nuevo) -----
git ls-files -co --exclude-standard -z | tar --null -T - -cf - | tar -xf - -C "$FUENTE" 2>/dev/null
echo "Archivos analizados: $(find "$FUENTE" -type f | wc -l)"

# ----- Python del pipeline (bandit y pytest) -----
PY="$(command -v python3 || command -v python)"
if [ ! -d "$RAIZ/.venv-pipeline" ]; then "$PY" -m venv "$RAIZ/.venv-pipeline" >/dev/null; fi
VBIN="$RAIZ/.venv-pipeline/bin"; [ -d "$RAIZ/.venv-pipeline/Scripts" ] && VBIN="$RAIZ/.venv-pipeline/Scripts"
"$VBIN/python" -m pip install -q -r "$FUENTE/requirements-dev.txt" 2>&1 | tail -1

# ================= ETAPAS =================

e_secretos() {
  dk -v "$DOCKER_TMP/fuente:/src" "$IMG_GITLEAKS" dir /src --redact --no-banner -v
}
etapa "1. Secretos en el codigo (Gitleaks)" "cualquier secreto detectado (0 toleradas)" e_secretos

e_sast() {
  # Informativo: severidad MEDIA o mayor (no bloquea)
  "$VBIN/python" -m bandit -r "$FUENTE/app" -ll -q --exit-zero
  # Umbral que bloquea: severidad ALTA
  "$VBIN/python" -m bandit -r "$FUENTE/app" -lll -q
}
etapa "2. Analisis estatico del codigo (Bandit)" "1 o mas hallazgos de severidad ALTA" e_sast

e_pruebas() {
  (cd "$FUENTE" && "$VBIN/python" -m pytest -q tests)
}
etapa "3. Pruebas de las reglas de validacion (pytest)" "1 o mas pruebas fallidas" e_pruebas

e_dependencias() {
  trivy fs --scanners vuln --severity "$UMBRAL_SEV" --ignore-unfixed --exit-code 1 \
    /work/fuente/app
}
etapa "4. Dependencias vulnerables (Trivy)" "1 o mas CVE $UMBRAL_SEV con parche disponible" e_dependencias

e_iac() {
  trivy config --severity "$UMBRAL_SEV" --exit-code 1 --ignorefile /work/fuente/.trivyignore.yaml /work/fuente
}
etapa "5. Infraestructura como codigo y Dockerfiles (Trivy config)" "1 o mas fallas $UMBRAL_SEV de configuracion" e_iac

e_politica() {
  (cd "$FUENTE" && "$VBIN/python" pipeline/politica_dockerfile.py Dockerfile.api Dockerfile.worker)
}
etapa "6. Politica de Dockerfile endurecido" "version no fija, USER root, sin HEALTHCHECK o secreto en Dockerfile" e_politica

e_imagenes() {
  local ok=0
  for svc in api worker; do
    echo "--- construyendo clipshare-$svc:pipeline"
    docker build -q -f "$FUENTE/Dockerfile.$svc" -t "clipshare-$svc:pipeline" "$FUENTE" >/dev/null || { echo "Fallo el build de $svc"; return 1; }
    docker save "clipshare-$svc:pipeline" -o "$TMP/$svc.tar"
    echo "--- escaneando clipshare-$svc:pipeline"
    trivy image --input "/work/$svc.tar" --table-mode detailed --scanners vuln --severity "$UMBRAL_SEV" --ignore-unfixed --exit-code 1 || ok=1
  done
  return $ok
}
etapa "7. Imagenes de contenedor (build + Trivy image)" "1 o mas CVE $UMBRAL_SEV con parche disponible en api o worker" e_imagenes

e_sbom() {
  mkdir -p reportes
  trivy image --input /work/worker.tar --format cyclonedx --output /work/sbom.json >/dev/null 2>&1 || { echo "No se pudo generar el SBOM"; return 1; }
  cp "$TMP/sbom.json" reportes/sbom_cyclonedx.json
  "$VBIN/python" - <<'PY'
import json, sys
d = json.load(open("reportes/sbom_cyclonedx.json"))
n = len(d.get("components", []))
print(f"SBOM CycloneDX {d.get('specVersion')} con {n} componentes")
sys.exit(0 if d.get("bomFormat") == "CycloneDX" and n > 0 else 1)
PY
}
etapa "8. SBOM CycloneDX" "SBOM invalido o sin componentes" e_sbom

# ================= VEREDICTO UNICO =================
echo
echo "=================================================================="
echo " RESUMEN DEL PIPELINE"
echo "=================================================================="
FALLOS=0
for r in "${RESULTADOS[@]}"; do
  IFS='|' read -r estado nombre umbral <<<"$r"
  if [ "$estado" = "OK" ]; then printf "  [ OK  ] %s\n" "$nombre"
  else printf "  [FALLO] %s\n           bloquea con: %s\n" "$nombre" "$umbral"; FALLOS=$((FALLOS+1)); fi
done
echo
if [ "$FALLOS" -gt 0 ]; then
  echo "VEREDICTO FINAL: DESPLIEGUE BLOQUEADO ($FALLOS de ${#RESULTADOS[@]} etapas fallaron)"
  rm -rf "$TMP"; exit 1
fi
echo "VEREDICTO FINAL: DESPLIEGUE PERMITIDO (${#RESULTADOS[@]} de ${#RESULTADOS[@]} etapas aprobadas)"
rm -rf "$TMP"; exit 0
