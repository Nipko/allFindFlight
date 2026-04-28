#!/usr/bin/env bash
# Bootstrap de un VPS Ubuntu limpio (22.04 / 24.04) para correr AllfindFlight.
# Instala: Docker Engine + Compose plugin + Portainer CE + UFW (SSH only).
# No abre puertos de la app: el ingress entra por Cloudflare Tunnel.
#
# Uso (como root o con sudo):
#   curl -fsSL https://raw.githubusercontent.com/Nipko/allFindFlight/main/infra/setup-vps.sh | bash
# o tras clonar:
#   sudo bash infra/setup-vps.sh

set -euo pipefail

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
apt-get install -y ca-certificates curl gnupg ufw

echo "==> Instalando Docker Engine"
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

echo "==> Instalando Portainer CE"
docker volume create portainer_data >/dev/null
if docker ps -a --format '{{.Names}}' | grep -q '^portainer$'; then
  echo "    Portainer ya existe, salto."
else
  docker run -d \
    -p 9443:9443 \
    --name portainer --restart=always \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v portainer_data:/data \
    portainer/portainer-ce:latest
fi

echo "==> Configurando UFW (SSH + Portainer admin)"
ufw allow OpenSSH >/dev/null
ufw allow 9443/tcp comment 'Portainer admin' >/dev/null
yes | ufw enable >/dev/null

echo "==> Resumen"
docker --version
docker compose version
echo "Portainer: https://$(hostname -I | awk '{print $1}'):9443"
echo "Listo. La app no expone puertos: el tráfico público entra por Cloudflare Tunnel."
