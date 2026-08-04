# Deploying to a Digital Ocean Droplet

Step-by-step guide for standing up `transpower-conductor-noise-tool-2026` in production on a fresh Digital Ocean Droplet running Ubuntu 24.04, pointed at the existing managed MySQL database, fronted by nginx + Let's Encrypt TLS, with daily cron jobs for ingestion and the two derived-data regeneration scripts.

Replace `noise.transpower.example` throughout with your real domain once chosen, and `<origin-url>` with this repo's real git remote.

## 1. Prerequisites

- A Droplet created (Ubuntu 24.04, at least 2GB RAM recommended — `pip install` pulls in `build-essential` and MySQL client headers).
- SSH key access to the Droplet as a sudo-capable user.
- A DNS A (and AAAA, if using IPv6) record for `noise.transpower.example` pointed at the Droplet's IP address — **your own step**, not covered here. TLS issuance in step 7 will fail until this resolves.

## 2. Base server setup

```bash
sudo apt update && sudo apt upgrade -y

# Firewall
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# Docker Engine + Compose plugin (official Docker apt repo, Ubuntu 24.04 "noble")
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# nginx + certbot
sudo apt install -y nginx python3-certbot-nginx
```

Add your deploy user to the `docker` group so you don't need `sudo` for every `docker compose` call: `sudo usermod -aG docker $USER` (log out/in to pick it up).

## 3. Transfer the app

```bash
sudo mkdir -p /opt/transpower-conductor-noise-tool-2026
sudo chown $USER:$USER /opt/transpower-conductor-noise-tool-2026
git clone <origin-url> /opt/transpower-conductor-noise-tool-2026
cd /opt/transpower-conductor-noise-tool-2026
```

## 4. Secrets

```bash
cp .env.example .env
chmod 600 .env
```

Edit `.env` and fill in real values:
- `DATABASE_URL` — the managed MySQL connection string, pointed at the existing `production` schema (already fully populated and schema-current — not `defaultdb`, DigitalOcean's empty default schema), keeping `ssl_ca=/app/ca-certificate.crt` (that's the path *inside* every container, not on the host).
- `NW_USERNAME` / `NW_PASSWORD` / `NW_BASE_URL` / `INGEST_SITE_IDS` — real Noise and Weather API credentials and site scope.
- `SECRET_KEY` — generate a real one, don't reuse the dev default:
  ```bash
  python3 -c "import secrets; print(secrets.token_hex(32))"
  ```
- `SESSION_COOKIE_SECURE=true` (the app is served over HTTPS once step 7 is done).

Copy the MySQL CA certificate to the repo root (it's gitignored, never in the repo — copy it from wherever you're managing it, e.g. `scp`):

```bash
scp ca-certificate.crt youruser@<droplet-ip>:/opt/transpower-conductor-noise-tool-2026/ca-certificate.crt
```

## 5. Bring up the app

```bash
docker compose -f docker-compose.prod.yml build

docker compose -f docker-compose.prod.yml up -d web
docker compose -f docker-compose.prod.yml logs -f web   # confirm gunicorn started cleanly, Ctrl-C to stop following
```

No `db-migrate` step here: the `production` schema already exists, is fully populated, and is kept in sync by hand via direct SQL (see `CLAUDE.md`) — never by running this repo's own Alembic against it. `web` just connects straight to it via `DATABASE_URL`. The `db-migrate` image is still used below for one-off scripts (step 8's user-creation, step 9's cron jobs), just never invoked with its default `alembic upgrade head && seed_cli` command against this database.

`web` now listens on `127.0.0.1:5001` on the Droplet (not yet publicly reachable — that's what nginx is for next).

## 6. Host nginx reverse proxy

Create `/etc/nginx/sites-available/conductor-noise`:

```nginx
server {
    listen 80;
    server_name noise.transpower.example;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

(Same shape as this repo's `docker/nginx.conf`, used for the local `prodlike` Docker Compose profile — reused here as host config instead, pointed at `web`'s published port.)

```bash
sudo ln -s /etc/nginx/sites-available/conductor-noise /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 7. TLS

```bash
sudo certbot --nginx -d noise.transpower.example
```

This rewrites the site file to add a `listen 443 ssl` block and an HTTP→HTTPS redirect, and installs the certificate. Verify auto-renewal is active (the `certbot` apt package installs this automatically — no extra setup needed):

```bash
sudo systemctl status certbot.timer
```

## 8. Verify

```bash
curl https://noise.transpower.example/api/health
```

Then log in via browser at `https://noise.transpower.example/login`.

**Note**: the managed database's existing real user accounts can't log in through this app (old, incompatible password hashes — a known limitation). Create a real working account:

```bash
docker compose -f docker-compose.prod.yml run --rm db-migrate \
  python scripts/create_external_test_user.py --email you@transpower.co.nz --password '<a-real-password>' --write-access
```

(Despite the filename, this script just creates any login-capable user with a correctly hashed password — reused here for production, not only the external-test workflow it was originally written for.)

## 9. Daily cron jobs

Create `/opt/transpower-conductor-noise-tool-2026/cron/run.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /opt/transpower-conductor-noise-tool-2026

job_name="$1"
shift

mkdir -p /var/log/conductor-noise
exec flock -n "/tmp/conductor-noise-${job_name}.lock" \
  bash -c "echo \"[\$(date -Is)] starting ${job_name}\" >> /var/log/conductor-noise/${job_name}.log; \
    $* >> /var/log/conductor-noise/${job_name}.log 2>&1; \
    echo \"[\$(date -Is)] finished ${job_name} (exit \$?)\" >> /var/log/conductor-noise/${job_name}.log"
```

```bash
chmod +x /opt/transpower-conductor-noise-tool-2026/cron/run.sh
sudo mkdir -p /var/log/conductor-noise
sudo chown $USER:$USER /var/log/conductor-noise
```

`flock -n` skips a run entirely (rather than queuing) if the previous run of the *same* job is still going — cheap insurance against a slow ingestion run overlapping with itself, not against the three different jobs overlapping each other (handled instead by staggering their start times below).

Add to the deploy user's crontab (`crontab -e`), staggered so ingestion has time to finish before the two regenerations read its output:

```cron
0 2 * * *  /opt/transpower-conductor-noise-tool-2026/cron/run.sh ingest "docker compose -f docker-compose.prod.yml --profile ingestion run --rm ingest"
30 2 * * * /opt/transpower-conductor-noise-tool-2026/cron/run.sh conductor-summary "docker compose -f docker-compose.prod.yml run --rm db-migrate python scripts/generate_conductor_summary.py"
45 2 * * * /opt/transpower-conductor-noise-tool-2026/cron/run.sh rain-rate-fits "docker compose -f docker-compose.prod.yml run --rm db-migrate python scripts/generate_rain_rate_fits.py"
```

If ingestion regularly takes longer than 30 minutes, push the later two jobs back further — check `/var/log/conductor-noise/ingest.log` after the first few real runs and adjust.

## 9a. Weekly derived-table regeneration

`wind_rose` and `monthly_rainfall` are precomputed from the raw `reading` table's full history (site-level wind rose + climatological monthly average rainfall, shown on the Locations tab when a site is clicked) via a single set-based SQL aggregation each (`ReadingRepository.aggregate_wind_rose`/`aggregate_monthly_rainfall`), not the pandas-based approach the daily `conductor-summary`/`rain-rate-fits` jobs above use — `reading` is a ~2.4M-row table, too large to pull wholesale into pandas the way those two jobs do against the much smaller `processed_reading` table. Both are cheap enough, and change slowly enough, to regenerate weekly rather than daily.

Reuses the same `cron/run.sh` wrapper as the daily jobs above (no new infra needed). Add to the deploy user's crontab (`crontab -e`), a full hour clear of the daily jobs' latest possible start and staggered from each other:

```cron
0 3 * * 0  /opt/transpower-conductor-noise-tool-2026/cron/run.sh wind-rose "docker compose -f docker-compose.prod.yml run --rm db-migrate python scripts/generate_wind_rose.py"
15 3 * * 0 /opt/transpower-conductor-noise-tool-2026/cron/run.sh monthly-rainfall "docker compose -f docker-compose.prod.yml run --rm db-migrate python scripts/generate_monthly_rainfall.py"
```

Sunday 3am (`0 3 * * 0`). These read `reading` directly, so they only need the 2am `ingest` job's raw-row upsert to have completed by 3am — not the two derived-`processed_reading` jobs that follow it.

## 9b. Memory/OOM watchdog

The Droplet has no swap and (before the `mem_limit` added to `docker-compose.prod.yml`) no cgroup memory boundary on the `web` container, so a runaway query could exhaust host RAM and let the kernel OOM killer take out unrelated host processes (sshd, VS Code Remote-SSH) — not just the app. `cron/watchdog.sh` is a cheap early-warning check: it logs a warning line to `/var/log/conductor-noise/watchdog.log` whenever available memory drops below 300MB, the kernel has logged an OOM/SIGKILL event in the last 5 minutes, or `conductor_noise_2026_web`'s gunicorn worker was SIGKILLed in the last 5 minutes.

```bash
chmod +x /opt/transpower-conductor-noise-tool-2026/cron/watchdog.sh
```

Add to the deploy user's crontab (`crontab -e`):

```cron
*/5 * * * * /opt/transpower-conductor-noise-tool-2026/cron/watchdog.sh
```

Check `/var/log/conductor-noise/watchdog.log` (or `tail -f` it) if the app or the Droplet itself becomes unresponsive.

### Manual triage runbook

If the app or SSH/VS Code becomes unresponsive, check in this order:
```bash
free -h                                                              # current memory/swap pressure
journalctl --list-boots                                              # did the whole VM reboot, not just the container
docker logs --since 1h conductor_noise_2026_web | grep -i "sigkill\|oom\|timeout"  # worker kills / loopback timeouts
docker inspect conductor_noise_2026_web --format '{{.State.Health.Status}}'        # container healthcheck status
cat /var/log/conductor-noise/watchdog.log                            # watchdog warnings, if cron job 9b is installed
```

## 10. Docker log rotation

Container logs (`web`, `ingest`) grow unbounded by default. Create `/etc/docker/daemon.json`:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

```bash
sudo systemctl restart docker
```

(Applies to newly-created containers — re-run `docker compose -f docker-compose.prod.yml up -d web` afterwards so it picks up the new default.)

## 11. Updating the app later

```bash
cd /opt/transpower-conductor-noise-tool-2026
git pull
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d web
```

If a code change needs a schema change, apply it by hand with direct SQL against the `production` schema (matching how it's been kept in sync so far — see `CLAUDE.md`), not by running this repo's `alembic upgrade head` against it.

## 12. Backups

The managed MySQL database has its own Digital Ocean backup story — not duplicated here. `conductor_summary` and `rain_rate_fit` are both fully derived from `processed_reading` and can be regenerated at any time via the two scripts above, so they don't need separate backup either.
