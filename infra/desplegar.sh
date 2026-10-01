#!/usr/bin/env bash
# Despliega la app en la EC2 por SSM (sin SSH ni llaves).
# Uso (con credenciales de AWS ya cargadas en el entorno):
#   ./infra/desplegar.sh <id-de-instancia>
# Empaqueta lo que git subiria + tu .env local, lo deja un momento en el bucket
# (privado y cifrado), lo baja en la instancia, levanta docker compose y borra el paquete.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
INSTANCIA="${1:?Uso: $0 <id-de-instancia>}"
BUCKET="$(grep '^S3_BUCKET=' .env | cut -d= -f2)"
TAR="$(mktemp -u).tar"; PAQUETE="$TAR.gz"
CLAVE="deploy/clipshare.tgz"

# codigo que git subiria + el .env local (esta en .gitignore a proposito)
git ls-files -co --exclude-standard -z | tar --null -T - -cf "$TAR"
tar -rf "$TAR" .env
gzip -c "$TAR" > "$PAQUETE"; rm -f "$TAR"

aws s3 cp "$PAQUETE" "s3://$BUCKET/$CLAVE" --only-show-errors
rm -f "$PAQUETE"

COMANDOS='set -e; [ -x /usr/local/lib/docker/cli-plugins/docker-buildx ] || { curl -fsSL https://github.com/docker/buildx/releases/download/v0.30.1/buildx-v0.30.1.linux-amd64 -o /usr/local/lib/docker/cli-plugins/docker-buildx; chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx; }; mkdir -p /opt/clipshare; cd /opt/clipshare; aws s3 cp s3://'"$BUCKET/$CLAVE"' /tmp/clipshare.tgz --only-show-errors; tar -xzf /tmp/clipshare.tgz; rm -f /tmp/clipshare.tgz; chmod 600 .env; docker compose up -d --build 2>&1 | tail -15; docker compose ps'
ID=$(aws ssm send-command --instance-ids "$INSTANCIA" --document-name AWS-RunShellScript \
  --parameters "commands=[\"$COMANDOS\"]" --timeout-seconds 900 --query Command.CommandId --output text)
echo "Comando SSM: $ID (esperando...)"
while :; do
  ESTADO=$(aws ssm get-command-invocation --command-id "$ID" --instance-id "$INSTANCIA" --query Status --output text 2>/dev/null || echo Pending)
  case "$ESTADO" in Success|Failed|Cancelled|TimedOut) break;; esac; sleep 8
done
aws ssm get-command-invocation --command-id "$ID" --instance-id "$INSTANCIA" --query '[StandardOutputContent,StandardErrorContent]' --output text
aws s3 rm "s3://$BUCKET/$CLAVE" --only-show-errors
echo "Estado final: $ESTADO"
[ "$ESTADO" = "Success" ]
