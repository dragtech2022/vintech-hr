# Install VINTECH HR on your separate Ubuntu server

Use a new folder on the **separate server**. These commands do not belong inside a Frappe container or `bench console`. This app creates its own Docker project and SQLite database. No changes to live ERPNext or your existing reverse proxy are required for the initial tunnel test.

## 1. Check prerequisites — Ubuntu SSH terminal

```bash
docker --version
```

```bash
docker compose version
```

If either is missing, install Docker Engine and the Compose plugin using Docker's official Ubuntu instructions: https://docs.docker.com/engine/install/ubuntu/ . This package does not run a remote install script. Your Linux account must be allowed to run Docker (or use `sudo docker` consistently). Docker group membership grants root-equivalent access.

## 2. Transfer and extract

Download `vintech-hr-community-v0.2.0.zip` to Windows. In PowerShell, replace `YOUR_USER` and `YOUR_SERVER_IP` with the new server's details. Adjust the local ZIP path if it is not in Downloads:

```powershell
scp "$env:USERPROFILE\Downloads\vintech-hr-community-v0.2.0.zip" YOUR_USER@YOUR_SERVER_IP:~/
```

In the **Ubuntu SSH terminal**, extract into your home directory (new installation only):

```bash
cd ~
```

```bash
python3 -m zipfile -e vintech-hr-community-v0.2.0.zip .
```

```bash
cd ~/vintech-hr-standalone
```

If this folder already contains a running installation, stop here and back it up before replacing files. Do not use new-install commands as an unreviewed upgrade.

## 3. Create configuration

This command preserves an existing `.env`:

```bash
test -f .env || cp .env.example .env
```

Default `.env`:

```ini
HR_BIND_ADDRESS=127.0.0.1
HR_PORT=8088
HR_COOKIE_SECURE=false
```

The default port is reachable only from the Ubuntu server or through your SSH tunnel. It is not opened on all interfaces.

## 4. Build and start — Ubuntu SSH terminal

```bash
docker compose up -d --build
```

```bash
docker compose ps
```

```bash
curl --fail http://127.0.0.1:8088/healthz
```

Expected JSON includes `"status":"ok"` and version `0.2.0`. The first build needs internet access to download the Python base image and packages. There are no cloud API requirements after installation.

## 5. Create your administrator — Ubuntu SSH terminal

```bash
docker compose exec app python manage.py admin
```

Enter a username and a password of at least 12 characters. The password input is hidden. There is no shipped default password. Running this command for an existing username resets its password and revokes that account's sessions.

## 6. Open it privately — Windows PowerShell

Run in a **separate Windows PowerShell window**, replacing the server details:

```powershell
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:18088:127.0.0.1:8088 YOUR_USER@YOUR_SERVER_IP
```

Keep that window open. Visit:

**http://127.0.0.1:18088**

Sign in with the administrator you created. First create your shifts, then employees and their allowed shifts. Example values shown in a new shift form are editable starting values, not confirmed Vintech attendance rules. Nothing is saved until you click Save.

## 7. Domain access through your existing HTTPS proxy

Do this after the tunnel test works. Choose the new HR hostname separately; do not replace `erp.vintechind.com` or assume you control the existing `vintech.vishvahr.in` service.

- Point the chosen hostname to your existing reverse proxy.
- If the proxy is on another machine, set `HR_BIND_ADDRESS` to **the new HR server's private LAN IP**, and set its upstream to `http://NEW_HR_SERVER_LAN_IP:8088`.
- If the proxy runs on the same host outside Docker, retain loopback binding and use `http://127.0.0.1:8088`.
- If the proxy is containerized on the same host, its `127.0.0.1` is not the host. Use an explicitly reachable host address or shared Docker network in a reviewed override.
- Preserve the browser's original `Host` header when forwarding. The app does not trust `X-Forwarded-*` for authentication or client identity.
- Terminate TLS at the proxy and use a valid certificate. Set `HR_COOKIE_SECURE=true` in `.env` when browser access is HTTPS.
- Restrict upstream port 8088 to the proxy host using the appropriate network/Docker firewall rules. Do not assume a host firewall alone restricts Docker-published ports.
- No new Traefik or Nginx service is included.

Apply configuration changes:

```bash
docker compose up -d
```

With secure cookies enabled, plain HTTP login through the SSH URL will no longer retain the session. Use the HTTPS hostname, or return to the explicit tunnel configuration for local testing. The deployment is admin-only; don't give employee users admin credentials.

## Backups

From `~/vintech-hr-standalone`:

```bash
bash scripts/backup.sh
```

This uses SQLite's online backup API, validates database integrity and writes a timestamped file to `backups/` with private permissions. It includes employees, shifts, users, password hashes and sessions. Keep it private and copy it to another disk/server. Also keep the exact source ZIP and `.env` separately. There is no scheduled backup until you configure one.

Do not copy only `hr.sqlite3` while it is running: pending transactions can be in its WAL file.

### Restore only when deliberately requested

Restoring replaces the current HR database. First make a fresh backup. The following example restores a chosen backup into this app's volume, with the service stopped. Replace the timestamp below with your exact backup filename.

```bash
docker compose stop app
```

```bash
docker compose run --rm -T -v "$PWD/backups:/restore:ro" app python - <<'PY'
import os
import sqlite3
from pathlib import Path
source = Path('/restore/hr-YOUR_BACKUP_TIMESTAMP.sqlite3')
if not source.is_file():
    raise SystemExit('Backup not found; database unchanged.')
src = sqlite3.connect(f'file:{source}?mode=ro', uri=True)
if src.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
    raise SystemExit('Backup integrity failed; database unchanged.')
if src.execute('SELECT version FROM schema_version').fetchone()[0] != 1:
    raise SystemExit('Unsupported backup schema; database unchanged.')
dst = sqlite3.connect(os.environ['HR_DATABASE'])
src.backup(dst)
dst.execute('DELETE FROM sessions')
dst.execute('DELETE FROM attempts')
dst.commit()
dst.close()
src.close()
print('Restored; all sessions revoked.')
PY
```

```bash
docker compose up -d
```

## Useful commands

View logs:

```bash
docker compose logs --tail=100 app
```

Stop without deleting the database:

```bash
docker compose down
```

Start again:

```bash
docker compose up -d
```

**Do not run `docker compose down -v` or prune this project's volume: those actions delete persistent HR data.** Keep this project name separate from all ERP projects.

## Verification scope

Backend security/persistence tests and JavaScript syntax checks were run during packaging. The Docker CLI is unavailable in the build environment, so image building and your server's reverse-proxy configuration must be verified on Ubuntu. This package does not claim production payroll readiness.
