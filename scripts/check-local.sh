#!/bin/sh
# Daily local check. Credentials and reports stay outside the checkout.
set -eu
umask 077
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
config=${CF_CERT_MONITOR_CONFIG:-${XDG_CONFIG_HOME:-$HOME/.config}/cf-cert-monitor/config.json}
state_dir=${CF_CERT_MONITOR_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/cf-cert-monitor}
if [ ! -r "$config" ]; then
  echo "Local Cloudflare configuration is missing: $config" >&2
  exit 1
fi
mkdir -p "$state_dir"
cd "$state_dir"
exec "$repo_dir/.venv/bin/cf-cert-monitor" --config "$config" --fail-on-expiring --no-report
