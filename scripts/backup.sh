#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
umask 077
mkdir -p backups
backup_path="backups/hr-$(date -u +%Y%m%dT%H%M%SZ)-${RANDOM}.sqlite3"
trap 'rm -f "$backup_path.tmp"' EXIT
docker compose exec -T app python scripts/backup_stdout.py > "$backup_path.tmp"
test -s "$backup_path.tmp"
mv "$backup_path.tmp" "$backup_path"
echo "Verified database backup: $backup_path"
