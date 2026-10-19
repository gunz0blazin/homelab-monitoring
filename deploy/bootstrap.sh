#!/bin/sh
# One-time setup on the Docker host. Takes over the hand-made stack in /opt/monitoring.
#
#   git clone <this repo's URL> /tmp/homelab-monitoring
#   sudo /tmp/homelab-monitoring/deploy/bootstrap.sh
#
# Installs the deploy command and the 5-minute timer and runs the first deploy. The first
# deploy recreates the Prometheus container (its config is now mounted as a folder); the
# data volumes are kept. /opt/monitoring is left untouched as a way back:
#   cd /opt/monitoring && docker compose -p monitoring up -d
# Safe to run again.
set -eu

CONF=/etc/monitoring-deploy
HERE=$(cd "$(dirname "$0")" && pwd)

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root." >&2; exit 1
fi

command -v docker >/dev/null 2>&1 || { echo "Docker isn't installed on this machine." >&2; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "The 'docker compose' plugin is missing." >&2; exit 1; }

# The stack must keep using its existing data. If these volumes are missing, the deploy
# would start empty ones, so stop unless told otherwise.
if [ "${FORCE:-}" != 1 ]; then
  for v in monitoring_prometheus-data monitoring_grafana-data; do
    docker volume inspect "$v" >/dev/null 2>&1 || {
      echo "Docker volume $v not found, so this isn't the stack I expected." >&2
      echo "Run with FORCE=1 to start with empty data anyway." >&2
      exit 1
    }
  done
fi

echo "==> Packages"
apt-get update -qq
apt-get install -y git curl python3-yaml

echo "==> Settings in $CONF"
install -d -m 0700 "$CONF"
install -d -m 0755 "$CONF/secrets"    # credential files Prometheus reads; see CLAUDE.md
if [ ! -e "$CONF/deploy.env" ]; then
  REPO_URL_VALUE=${REPO_URL:-}
  if [ -z "$REPO_URL_VALUE" ]; then
    REPO_URL_VALUE=$(git -C "$HERE" remote get-url origin 2>/dev/null || true)
  fi
  [ -n "$REPO_URL_VALUE" ] || { echo "Set REPO_URL=<repo URL> and run again." >&2; exit 1; }
  cat > "$CONF/deploy.env" <<EOT
# Which repo and branch this machine deploys.
REPO_URL=$REPO_URL_VALUE
BRANCH=${BRANCH:-main}
EOT
  chmod 0600 "$CONF/deploy.env"
fi

if [ ! -e "$CONF/ntfy_url" ]; then
  printf '    ntfy topic URL for deploy notifications (Enter to skip): '
  read -r ntfy
  [ -n "$ntfy" ] && { printf '%s' "$ntfy" > "$CONF/ntfy_url"; chmod 0600 "$CONF/ntfy_url"; }
fi

echo "==> Deploy command and timer"
install -m 0755 "$HERE/monitoring-deploy" /usr/local/bin/monitoring-deploy
install -m 0644 "$HERE/systemd/monitoring-deploy.service" /etc/systemd/system/
install -m 0644 "$HERE/systemd/monitoring-deploy.timer" /etc/systemd/system/
systemctl daemon-reload

echo "==> First deploy"
/usr/local/bin/monitoring-deploy
# From here on the command is the repo's own copy, so script changes need no re-install.
ln -sf /opt/monitoring-repo/repo/deploy/monitoring-deploy /usr/local/bin/monitoring-deploy
systemctl enable --now monitoring-deploy.timer

echo
echo "Done. Monitoring now updates within 5 minutes of a push to the repo."
echo "  Watch it:   journalctl -u monitoring-deploy -f"
echo "  Run it now: monitoring-deploy"
