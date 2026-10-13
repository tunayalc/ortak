#!/usr/bin/env bash
set -euo pipefail

# Run only after Oracle free eligibility and SSH authorization are verified.
if [ "$(uname -m)" != "aarch64" ]; then
  printf '%s\n' 'Expected the approved ARM64 server; nothing installed.' >&2
  exit 1
fi
if [ "$(id -u)" -ne 0 ]; then
  printf '%s\n' 'Run with sudo on the approved server.' >&2
  exit 1
fi
. /etc/os-release
if [ "$ID" != ubuntu ] || [ "$VERSION_ID" != 24.04 ]; then
  printf '%s\n' 'Expected Ubuntu 24.04; no alternative image or paid resource selected.' >&2
  exit 1
fi
apt-get update
apt-get install -y ca-certificates curl git python3
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Architectures: arm64
Signed-By: /etc/apt/keyrings/docker.asc
EOF
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
if [ ! -d /opt/ortak/.git ]; then
  git clone https://github.com/tunayalc/ortak.git /opt/ortak
fi
install -d -m 700 -o 10001 -g 10001 /opt/ortak/deploy/data /opt/ortak/deploy/guard /opt/ortak/deploy/backups
install -d -m 700 /opt/ortak/deploy/private
printf '%s\n' 'Docker installed. No Google key, billing change, model download or firewall opening performed.'
