#!/usr/bin/env bash
set -euo pipefail

platform_id() {
  case "$1:$2" in
    ubuntu:24.04) printf '%s\n' ubuntu-24.04 ;;
    ol:9|ol:9.[0-9]*) printf '%s\n' oracle-linux-9 ;;
    *) printf '%s\n' 'Expected Oracle Linux 9 or Ubuntu 24.04; nothing installed.' >&2; return 1 ;;
  esac
}

if [ "${1:-}" = --check-platform ]; then
  if [ "$#" -ne 3 ]; then
    printf '%s\n' 'Usage: bootstrap.sh --check-platform OS_ID VERSION_ID' >&2
    exit 1
  fi
  platform_id "$2" "$3"
  exit
fi

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
platform=$(platform_id "$ID" "$VERSION_ID")
case "$platform" in
  ubuntu-24.04)
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
    ;;
  oracle-linux-9)
    dnf install -y ca-certificates curl git python3 gnupg2 dnf-plugins-core
    key_file=$(mktemp)
    trap 'rm -f "$key_file"' EXIT
    curl -fsSL https://download.docker.com/linux/centos/gpg -o "$key_file"
    fingerprint=$(gpg --batch --show-keys --with-colons "$key_file" | awk -F: '$1 == "fpr" {print $10; exit}')
    if [ "$fingerprint" != 060A61C51B558A7F742B77AAC52FEB6B621E9F35 ]; then
      printf '%s\n' 'Docker signing key changed; review it before installing packages.' >&2
      exit 1
    fi
    rpm --import "$key_file"
    # Pin EL9, not an Oracle minor release such as 9.7, in the vendor repository URL.
    cat > /etc/yum.repos.d/ortak-docker-ce.repo <<'EOF'
[ortak-docker-ce-stable]
name=Docker CE Stable - EL9
baseurl=https://download.docker.com/linux/centos/9/$basearch/stable
enabled=1
gpgcheck=1
gpgkey=https://download.docker.com/linux/centos/gpg
EOF
    dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    install -d -m 0755 /etc/docker
    python3 -c 'import json,os,tempfile; from pathlib import Path; p=Path("/etc/docker/daemon.json"); data=json.loads(p.read_text()) if p.exists() else {}; data["selinux-enabled"]=True; fd,name=tempfile.mkstemp(dir=p.parent); os.fchmod(fd,0o600); f=os.fdopen(fd,"w"); json.dump(data,f); f.flush(); os.fsync(f.fileno()); f.close(); os.replace(name,p)'
    ;;
esac
systemctl enable --now docker
docker info >/dev/null
docker compose version
if [ ! -d /opt/ortak/.git ]; then
  git clone https://github.com/tunayalc/ortak.git /opt/ortak
fi
install -d -m 700 -o 10001 -g 10001 /opt/ortak/deploy/data /opt/ortak/deploy/guard /opt/ortak/deploy/backups
install -d -m 700 /opt/ortak/deploy/private
printf '%s\n' 'Docker installed. No Google key, billing change, model download or firewall opening performed.'
