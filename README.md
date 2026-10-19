# homelab-monitoring

Prometheus, Grafana and Uptime Kuma for my home lab, deployed by pushing to this repo.

```
push to main  ->  GitHub  ->  Docker host pulls every 5 min  ->  Prometheus reloads
```

The Docker host makes an outbound connection to GitHub, so nothing needs to be opened on the network and no webhook is needed.

## Changing what's monitored

Edit `prometheus/prometheus.yml` or add a file under `prometheus/targets/`, commit, push to `main`. Within 5 minutes Prometheus has it. A commit that fails `promtool check config`, or whose YAML or compose file is broken, is skipped and reported (ntfy, if configured); the stack keeps its last good version.

## One-time setup on the Docker host

This takes over the hand-made stack in `/opt/monitoring`. The data volumes are kept; only the Prometheus container is recreated (a few seconds without scraping). `/opt/monitoring` is left untouched as a way back.

```
git clone <this repo's URL> /tmp/homelab-monitoring
sudo /tmp/homelab-monitoring/deploy/bootstrap.sh
```

The bootstrap refuses to run if the `monitoring_*` data volumes don't exist, so it can't quietly start with empty ones.

To go back to the hand-made setup: `systemctl disable --now monitoring-deploy.timer && cd /opt/monitoring && docker compose -p monitoring up -d`.

Useful commands on the host:

```
journalctl -u monitoring-deploy -f      # watch deploys
monitoring-deploy                       # deploy right now
systemctl list-timers monitoring-deploy.timer
```

Notifications are optional: a topic URL in `/etc/monitoring-deploy/ntfy_url`, and a token in `ntfy_token` for a protected topic.

No secrets live in this repo. Credentials are files in `/etc/monitoring-deploy/secrets/` on the host.
