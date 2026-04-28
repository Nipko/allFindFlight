#!/usr/bin/env bash
# Update + (re)deploy del stack en producción.
#
# Uso (como root o con sudo, desde cualquier ruta):
#   sudo /opt/allfindflight/infra/deploy.sh
#
# Hace: git pull, docker compose pull, docker compose up -d (recrea solo lo que cambió).

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${REPO_DIR}/infra/docker-compose.prod.yml"
ENV_FILE="${REPO_DIR}/infra/.env.prod"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Falta ${ENV_FILE}. Copia .env.prod.example y completa POSTGRES_PASSWORD y TUNNEL_TOKEN." >&2
  exit 1
fi

cd "${REPO_DIR}"

echo "==> git pull"
git pull --ff-only

echo "==> docker compose pull"
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" pull

echo "==> docker compose up -d"
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" up -d --remove-orphans

echo "==> ps"
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" ps
