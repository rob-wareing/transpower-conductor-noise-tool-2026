#!/usr/bin/env bash
# Lightweight memory/OOM watchdog for the Droplet running this app.
# Logs a warning line whenever available memory drops below a threshold or
# the kernel has logged an OOM/SIGKILL event recently, so a crash shows up
# in a log before it takes the whole box down again.
set -euo pipefail

LOG_DIR="/var/log/conductor-noise"
LOG_FILE="${LOG_DIR}/watchdog.log"
THRESHOLD_MB=300

mkdir -p "$LOG_DIR"

available_mb=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)

if [ "$available_mb" -lt "$THRESHOLD_MB" ]; then
  echo "[$(date -Is)] WARNING: low memory - ${available_mb}MB available (threshold ${THRESHOLD_MB}MB)" >> "$LOG_FILE"
fi

if journalctl -k -q --since "-5 min" 2>/dev/null | grep -qi "out of memory\|killed process"; then
  echo "[$(date -Is)] WARNING: kernel OOM event in the last 5 minutes" >> "$LOG_FILE"
fi

if docker logs --since 5m conductor_noise_2026_web 2>&1 | grep -qi "sigkill\|perhaps out of memory"; then
  echo "[$(date -Is)] WARNING: gunicorn worker SIGKILL in conductor_noise_2026_web in the last 5 minutes" >> "$LOG_FILE"
fi
