#!/usr/bin/env bash
# Preparación de la VM Ampere A1 (Oracle Linux 9 o Ubuntu 24.04). Se corre una sola vez.
set -euo pipefail

DOMINIO="${1:?Uso: setup-vm.sh <dominio> <email-letsencrypt> <url-del-repo>}"
EMAIL="${2:?}"
REPO="${3:?}"

if command -v dnf >/dev/null; then
  sudo dnf install -y git curl dnf-plugins-core
  sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
  sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  sudo firewall-cmd --permanent --add-service=http --add-service=https && sudo firewall-cmd --reload
else
  sudo apt-get update && sudo apt-get install -y git curl docker.io docker-compose-v2
fi
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

sudo mkdir -p /opt/mediflow && sudo chown "$USER" /opt/mediflow
git clone "$REPO" /opt/mediflow
cd /opt/mediflow
cp .env.example .env
echo "Edita /opt/mediflow/.env (OCI_AUTH=instance_principal, bucket, DSN, OCIDs) y copia el wallet a /opt/mediflow/wallet/"

# Certificado TLS (requiere que el dominio ya apunte a la IP pública y el puerto 80 abierto en la security list)
sudo docker run --rm -p 80:80 -v /etc/letsencrypt:/etc/letsencrypt certbot/certbot certonly --standalone \
  -d "$DOMINIO" --email "$EMAIL" --agree-tos --non-interactive
sed -i "s/DOMINIO/$DOMINIO/g" infra/nginx.conf

echo "Listo. Primer despliegue: docker compose -f infra/docker-compose.yml up -d --build"
