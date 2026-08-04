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