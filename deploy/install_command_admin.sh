#!/usr/bin/env bash
set -euo pipefail

# IAM approval and this OS privilege grant are separate, explicit installation gates.
if [ "$#" -ne 1 ] || [ "$1" != --confirmed-permanent-instance-access ]; then
  printf '%s\n' 'Explicit approval of persistent, single-instance command access is required; nothing installed.' >&2
  exit 2
fi
if [ "$(id -u)" -ne 0 ]; then
  printf '%s\n' 'Run as root on the explicitly approved Oracle instance.' >&2
  exit 1
fi
getent passwd ocarun >/dev/null
test -x /usr/bin/python3
test -x /usr/sbin/visudo
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
test "$source_dir" = /opt/ortak/deploy
if /usr/sbin/runuser -u ocarun -- sudo -n /usr/bin/id -u >/dev/null 2>&1; then
  printf '%s\n' 'Unexpected existing sudo access for ocarun; review it before installing this restricted rule.' >&2
  exit 1
fi

umask 077
install -d -o root -g root -m 0755 /usr/local/libexec /usr/local/sbin
install -o root -g root -m 0700 "$source_dir/command_admin.py" /usr/local/libexec/ortak-command-admin.py
launcher=$(mktemp)
rule=$(mktemp)
trap 'rm -f "$launcher" "$rule"' EXIT
printf '%s\n' '#!/bin/sh' 'exec /usr/bin/python3 -I /usr/local/libexec/ortak-command-admin.py "$@"' > "$launcher"
install -o root -g root -m 0755 "$launcher" /usr/local/sbin/ortak-admin
/usr/local/sbin/ortak-admin status >/dev/null
printf '%s\n' 'Defaults:ocarun env_reset' 'ocarun ALL=(root) NOPASSWD: NOSETENV: /usr/local/sbin/ortak-admin' > "$rule"
/usr/sbin/visudo -cf "$rule" >/dev/null
install -o root -g root -m 0440 "$rule" /etc/sudoers.d/101-ortak-command-admin
printf '%s\n' 'Restricted ORTAK command entry point installed. No IAM policy, SSH key, firewall or Google setting was changed.'
