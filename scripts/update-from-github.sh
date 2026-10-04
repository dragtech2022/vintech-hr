#!/usr/bin/env bash
# Updates only the existing VINTECH HR checkout and Docker project.
set -euo pipefail
umask 077
project_dir="${1:-/home/hyper/vintech-hr}"
cd "$project_dir"
project_dir="$(pwd -P)"
[ -f compose.yaml ] && [ -f .env ] || { echo 'Existing HR checkout/configuration not found.'; exit 1; }
[ "$(git remote get-url origin)" = 'https://github.com/dragtech2022/vintech-hr.git' ] || { echo 'Unexpected Git origin; stopped.'; exit 1; }
[ "$(git branch --show-current)" = main ] || { echo 'Expected the main branch; stopped.'; exit 1; }
git fetch origin main
git merge-base --is-ancestor HEAD origin/main || { echo 'Local commits diverge; stopped without changing source.'; exit 1; }
# Validate the target release before changing the working tree. Permit only the
# previously requested eight-character password modification locally.
python3 - <<'PY'
from pathlib import Path
import subprocess

def git(*args):
    return subprocess.check_output(['git',*args])

if b"VERSION = '0.3.0'" not in git('show','origin/main:app.py'):
    raise SystemExit('Upload and commit the v0.3.0 source to GitHub first. No changes made.')
changes=set(git('diff','--name-only','HEAD','-z').decode().split('\0'))-{''}
if changes-{'manage.py'}:
    raise SystemExit('Local changes need review before updating: '+', '.join(sorted(changes)))
if 'manage.py' in changes:
    original=git('show','HEAD:manage.py').decode()
    expected=original.replace('12 characters','8 characters').replace('len(password)<12','len(password)<8').replace('12–256','8–256')
    if Path('manage.py').read_text()!=expected:
        raise SystemExit('Unrecognized manage.py changes; stopped without overwriting them.')
untracked=set(git('ls-files','--others','--exclude-standard','-z').decode().split('\0'))-{''}
target=set(git('ls-tree','-r','--name-only','origin/main','-z').decode().split('\0'))-{''}
if untracked & target:
    raise SystemExit('Untracked files would be overwritten: '+', '.join(sorted(untracked & target)))
print('Git preflight passed.')
PY
release_stamp="$(date +%Y%m%d-%H%M%S)-$$"
backup_dir="$(dirname "$project_dir")/vintech-hr-update-backups/$release_stamp"
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
git rev-parse HEAD > "$backup_dir/previous-commit.txt"
tar --exclude=./.git --exclude=./.venv --exclude=./__pycache__ --exclude=./backups --exclude='*.zip' -czf "$backup_dir/source.tar.gz" .
app_container="$(docker compose ps -q app)"
[ -n "$app_container" ] || { echo 'HR container is not running; stopped.'; exit 1; }
old_image="$(docker inspect "$app_container" --format '{{.Image}}')"
rollback_tag="vintech-hr-community:rollback-$release_stamp"
docker image tag "$old_image" "$rollback_tag"
docker compose exec -T app python manage.py backup --output "/tmp/hr-before-$release_stamp.sqlite3"
docker cp "$app_container:/tmp/hr-before-$release_stamp.sqlite3" "$backup_dir/database.sqlite3"
chmod 600 "$backup_dir/database.sqlite3"
# Rollback uses the preserved image with the same volume. The 0.3.0 migration
# only adds tables, so it does not require restoring or overwriting the database.
printf 'services:\n  app:\n    image: %s\n' "$rollback_tag" > "$backup_dir/rollback-image.yaml"
printf 'Backup folder: %s\n' "$backup_dir"
printf 'If needed, roll back the running app with:\n'
printf 'cd %q && docker compose -f compose.yaml -f %q up -d --no-build --wait app\n' "$project_dir" "$backup_dir/rollback-image.yaml"
if ! git diff --quiet HEAD -- manage.py; then
    git restore --source=HEAD --staged --worktree -- manage.py
fi
git merge --ff-only origin/main
sha256sum -c SHA256SUMS
docker compose build app
docker compose up -d --no-build --wait --wait-timeout 120 app
docker compose exec -T app python -c "import json,urllib.request; d=json.load(urllib.request.urlopen('http://127.0.0.1:8000/healthz')); assert d['version']=='0.3.0',d; print(d)"
printf '\nCompany Master update completed. Open https://hr.dragtech.in and refresh.\n'
