#!/usr/bin/env bash
# Bootstrap de un VPS Ubuntu limpio (22.04 / 24.04) para correr AllfindFlight nativo.
# Instala Docker Engine + Compose plugin, clona el repo en /opt/allfindflight,
# prepara .env.prod a partir del template y endurece UFW (solo SSH).
# El ingress entra por Cloudflare Tunnel; no se publica ningún puerto al host.
#
# Uso (como root o con sudo):
#   curl -fsSL https://raw.githubusercontent.com/Nipko/allFindFlight/main/infra/setup-vps.sh | sudo bash

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Nipko/allFindFlight.git}"
REPO_DIR="${REPO_DIR:-/opt/allfindflight}"
REPO_BRANCH="${REPO_BRANCH:-main}"

if [[ $EUID -ne 0 ]]; then
  echo "Ejecutar como root o con sudo." >&2
  exit 1
fi

. /etc/os-release
if [[ "${ID:-}" != "ubuntu" ]]; then
  echo "Este script asume Ubuntu. Detectado: ${ID:-desconocido}" >&2
  exit 1
fi

echo "==> Actualizando apt"
apt-get update -y
apt-get install -y ca-certificates curl gnupg git ufw

echo "==> Instalando Docker Engine + Compose plugin"
install -m 0755 -d /etc/apt/keyrings
if [[ ! -f /etc/apt/keyrings/docker.gpg ]]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
fi
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable --now docker

echo "==> Clonando repositorio en ${REPO_DIR}"
if [[ -d "${REPO_DIR}/.git" ]]; then
  git -C "${REPO_DIR}" fetch --all --prune
  git -C "${REPO_DIR}" checkout "${REPO_BRANCH}"
  git -C "${REPO_DIR}" pull --ff-only
else
  git clone --branch "${REPO_BRANCH}" "${REPO_URL}" "${REPO_DIR}"
fi

echo "==> Preparando .env.prod"
ENV_FILE="${REPO_DIR}/infra/.env.prod"
if [[ ! -f "${ENV_FILE}" ]]; then
  cp "${REPO_DIR}/infra/.env.prod.example" "${ENV_FILE}"
  chmod 600 "${ENV_FILE}"
  echo "    Creado ${ENV_FILE} (rellenar antes de levantar el stack)."
else
  echo "    ${ENV_FILE} ya existe, no se toca."
fi

chmod +x "${REPO_DIR}/infra/deploy.sh" 2>/dev/null || true

echo "==> Configurando UFW (solo SSH)"
ufw allow OpenSSH >/dev/null
yes | ufw enable >/dev/null

echo
echo "==> Listo"
docker --version
docker compose version
echo
echo "Siguiente paso:"
echo "  1. Editar ${ENV_FILE} con POSTGRES_PASSWORD y TUNNEL_TOKEN."
echo "  2. Ejecutar:  sudo ${REPO_DIR}/infra/deploy.sh"
echo "  3. Tras el primer arranque:"
echo "       sudo docker exec -it aff-backend python -m app.scripts.seed_airports"
