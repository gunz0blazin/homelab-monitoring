# homelab-monitoring

Prometheus, Grafana and Uptime Kuma for the home lab, on the Docker host (`192.168.20.13`; Prometheus `:9090`, Grafana `:3000` as `grafana.home`, Uptime Kuma `:3002` as `status.home`). A timer on that host pulls this repo every 5 minutes and applies it, so **pushing to `main` is the deploy**. There is no other step.

## How to make a change

- Add or remove something to scrape: a file in `prometheus/targets/` (picked up within a minute, no reload) or a job in `prometheus/prometheus.yml`.
- Containers, ports, retention, image versions: `docker-compose.yml`.
- Commit and push to `main`. The stack updates within 5 minutes (`monitoring-deploy` on the Docker host forces it).

## Rules

- **This repo is public.** Never commit secrets (API keys, tokens, passwords, the ntfy URL, SSH keys) or anything you wouldn't post publicly. Credentials live as files on the host in `/etc/monitoring-deploy/secrets/`, mounted read-only into the container, and Prometheus reads them with `password_file` / `credentials_file`. Check the diff before every push.
- The only thing this repo reveals is the lab's private addresses, which aren't reachable from outside the network. Don't add anything more sensitive.
- **The compose project name must stay `monitoring`.** The deploy runs `docker compose -p monitoring`, which keeps the existing data volumes (`monitoring_prometheus-data`, `monitoring_grafana-data`) attached. Renaming the project or the volumes starts empty ones and the history looks lost.
- Mount config as the **folder** `./prometheus`, never a single file: a deploy replaces files, and a single-file bind mount keeps showing the old copy.
- **Never send Prometheus SIGHUP right after (re)creating its container.** It only handles SIGHUP (reload) once it has finished starting; sent earlier, the signal kills it (exit 129) and `unless-stopped` does not bring it back. The deploy script waits for `/-/ready` first and fails the deploy if it never comes; keep it that way.
- The deploy command on the host, `/usr/local/bin/monitoring-deploy`, is a **symlink** to `/opt/monitoring-repo/repo/deploy/monitoring-deploy`, and the script runs itself from a temporary copy (the deploy replaces the file while it runs). A script change therefore takes effect on the run after the commit that contains it is applied. A change that makes the checks **stricter** is checked by the previous script, so put tooling changes and config changes in separate commits, tooling first.
- Credentials are files in `/etc/monitoring-deploy/secrets/` on the host (mounted at `/secrets` in the containers). `promtool` checks that files named in the config exist, so the deploy script and CI mount the real folder or a dummy one; keep both in step when a new secret is referenced.
- Keep a Prometheus config that `promtool check config` accepts; the server runs it on every commit and skips a commit that fails, keeping the last good version, and sends one ntfy message.
- Dashboards in `grafana/dashboards/` are the source of truth for the **Homelab** folder: Grafana won't save UI edits to them (`allowUiUpdates: false`), so change the JSON here. They pick the Prometheus data source with a `datasource` variable, so they work whatever the data source is called. Only the dashboards provisioning folder is mounted, so dashboards and data sources made in the UI are untouched.
- Grafana's other dashboards and data sources, and Uptime Kuma's monitors and notification settings, live in their own data volumes (made in each web UI), not in this repo. Back those volumes up before changing a major version.
- Image versions are pinned (Prometheus `v3.15.0` and Grafana `13.0.2`, the versions running when this repo took over; Uptime Kuma `2.5.6`), so an update only happens when this repo changes. To update, change the tag in `docker-compose.yml` and push; Grafana upgrades its own database on start and can't be rolled back, so back up the Grafana volume first.

## Layout

- `docker-compose.yml`: Prometheus, Grafana and Uptime Kuma
- `grafana/dashboards/`: dashboards as JSON, loaded into the **Homelab** folder in Grafana (provider in `grafana/provisioning/dashboards/`)
- `prometheus/prometheus.yml`: scrape jobs
- `prometheus/targets/`: lists of targets for `file_sd_configs`
- `deploy/monitoring-deploy`: the pull-validate-apply script (installed to `/usr/local/bin`)
- `deploy/systemd/`: the 5-minute timer
- `deploy/bootstrap.sh`: one-time setup on the Docker host
- `.github/workflows/checks.yml`: lint, compose and promtool checks
