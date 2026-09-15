#!/bin/bash
set -euo pipefail

echo "=== DevOps Platform Backup Job ==="
echo "Started at: $(date)"

# Configuration
RESTIC_REPO="${RESTIC_REPO:-/mnt/backups/restic-repo}"
RESTIC_PASSWORD="${RESTIC_PASSWORD:-devops-backup-password}"
DATA_PATH="${DATA_PATH:-/app}"

export RESTIC_REPOSITORY="$RESTIC_REPO"
export RESTIC_PASSWORD="$RESTIC_PASSWORD"

# Initialize repo if needed
if [ ! -d "$RESTIC_REPO" ]; then
  echo "Initializing restic repository..."
  restic init || true
fi

# Backup the data
echo "Backing up $DATA_PATH..."
restic backup "$DATA_PATH" \
  --tag "devops-app-backup" \
  --tag "$(date +%Y-%m-%d)" \
  --exclude '*.pyc' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache'

# Check backup integrity
echo "Checking backup integrity..."
restic check

# Cleanup old snapshots (retention policy)
echo "Applying retention policy..."
restic forget \
  --keep-daily 7 \
  --keep-weekly 4 \
  --keep-monthly 12 \
  --prune

echo "Backup completed successfully at: $(date)"
echo "Latest snapshots:"
restic snapshots --compact
