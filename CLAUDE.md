# homelab-monitoring

Prometheus and Grafana for the home lab, on the Docker host (`192.168.20.13`; Prometheus `:9090`, Grafana `:3000`, reachable as `grafana.home`). A timer on that host pulls this repo every 5 minutes and applies it, so **pushing to `main` is the deploy**. There is no other step.

## How to make a change

- Add or remove something to scrape: a file in `prometheus/targets/` (picked up within a minute, no reload) or a job in `prometheus/prometheus.yml`.
- Containers, ports, retention, image versions: `docker-compose.yml`.
- Commit and push to `main`. The stack updates within 5 minutes (`monitoring-deploy` on the Docker host forces it).

## Rules

- **This repo is public.** Never commit secrets (API keys, tokens, passwords, the ntfy URL, SSH keys) or anything you wouldn't post publicly. Credentials live as files on the host in `/etc/monitoring-deploy/secrets/`, mounted read-only into the container, and Prometheus reads them with `password_file` / `credentials_file`. Check the diff before every push.
- The only thing this repo reveals is the lab's private addresses, which aren't reachable from outside the network. Don't add anything more sensitive.
- **The compose project name must stay `monitoring`.** The deploy runs `docker compose -p monitoring`, which keeps the existing data volumes (`monitoring_prometheus-data`, `monitoring_grafana-data`) attached. Renaming the project or the volumes starts empty ones and the history looks lost.
- Mount config as the **folder** `./prometheus`, never a single file: a deploy replaces files, and a single-file bind mount keeps showing the old copy.
- Keep a Prometheus config that `promtool check config` accepts; the server runs it on every commit and skips a commit that fails, keeping the last good version, and sends one ntfy message.
- Grafana's dashboards and data sources live in its own data volume (made in the web UI), not in this repo.
- Prefer pinned image versions to `latest`, so an update only happens when this repo changes.

## Layout

- `docker-compose.yml`: Prometheus and Grafana
- `prometheus/prometheus.yml`: scrape jobs
- `prometheus/targets/`: lists of targets for `file_sd_configs`
- `deploy/monitoring-deploy`: the pull-validate-apply script (installed to `/usr/local/bin`)
- `deploy/systemd/`: the 5-minute timer
- `deploy/bootstrap.sh`: one-time setup on the Docker host
- `.github/workflows/checks.yml`: lint, compose and promtool checks
