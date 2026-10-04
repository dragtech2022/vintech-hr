# VINTECH HR Community v0.3.0

Company Master is now included. See [COMPANY-MASTER.md](COMPANY-MASTER.md) for features, limitations and the backed-up GitHub upgrade procedure.

# VINTECH HR Community 0.2.0

Independent, self-hosted company, employee and shift management. MIT licensed. Runs on an Ubuntu server using Docker Compose, Python/Flask, Gunicorn and SQLite. No Frappe, ERPNext, VishvaHR, ChatGPT, cloud account, paid API, CDN or external frontend service is required at runtime.

This is the **employee and shift foundation**, not a complete payroll or biometric attendance system. This is a new standalone project, not an upgrade/installable release of the earlier `vintech_hr` Frappe add-on. Do not install it with `bench` or point it at an ERP database.

## Included

- Admin login with scrypt password hashing; no default account or password.
- Revocable server-side sessions, 8-hour expiry, HTTP-only cookies, CSRF checks, login throttling and same-origin-only writes.
- Employee create/edit: code, name, department, designation, joining date, email, phone, monthly/daily pay basis and active/inactive status.
- Up to three allowed shifts per employee, or none while setting up. No single mandatory default shift.
- Shift create/edit with seven weekday schedules, next-day checkout, minimum full/half-day minutes, unpaid break and arrival-window settings.
- Duplicate code checks, input validation and optimistic version checks to prevent silently overwriting another administrator's changes.
- Employee search, active/all/inactive filter, CSV export with formula-injection escaping.
- Activity history for employee/shift creation and editing (last 100 actions in UI).
- Persistent local database, non-root Docker service, health checks and consistent SQLite backup script.
- Responsive interface with no bundled real employee data or screenshot copies.

## Not included yet

Biometric device connection, check-in storage, automatic shift selection, attendance calculation, shift overlap resolution, weekly-off/pay entitlement rules, effective-dated assignments, payroll, salary rates, leave, statutory returns, employee self-service, granular roles and employee document uploads. Settings saved in this release do **not** calculate attendance or salary. All created admin accounts have full access. Activity history records who changed which record; it is not a full before/after compliance audit.

Build these next against confirmed business rules. Retain previous shift definitions or export configuration before changing historical rules once attendance processing is introduced. This version has no attendance history to recalculate.

## Installation

Read [INSTALL-UBUNTU.md](INSTALL-UBUNTU.md). Default access uses a loopback port with an SSH tunnel. For a domain, put it behind your existing HTTPS reverse proxy. It does not install a second proxy or change another Docker project.

## Architecture

- `app.py`: same-origin JSON API, authentication, validation and SQLite schema.
- `manage.py`: initialize schema, create/reset administrators, verified backups.
- `templates/index.html`, `static/`: original responsive browser interface.
- `wsgi.py`: production Gunicorn entry point.
- `compose.yaml`: one app service and a dedicated `hr_data` volume.
- `tests/test_app.py`: isolated API/security/persistence tests.
- `scripts/backup.sh`: consistent database backup to a private local folder.

Database schema version is 1. Startup creates absent tables and rejects unknown schema versions. Future upgrades that change existing tables must supply an explicit migration and backup/restore instructions; `CREATE TABLE IF NOT EXISTS` is not a general migration framework. SQLite WAL is appropriate for a single-server foundation; do not share the live database volume over NAS or run replicas on different servers.

## Development

Python 3.12 is used by the Docker image. For a local development environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export HR_DATABASE="$PWD/dev.sqlite3"
export HR_COOKIE_SECURE=false
python manage.py init
python manage.py admin
gunicorn --bind 127.0.0.1:8088 --workers 2 --threads 2 wsgi:app
```

Open `http://127.0.0.1:8088`. Keep `dev.sqlite3`, `.env` and backups out of source control.

Run backend checks:

```bash
python -m unittest discover -s tests -v
node --check static/app.js
```

Node is needed only for the optional JavaScript syntax check, not for running the application.

## API

`POST /api/login`, `GET /api/me`, `POST /api/logout`, `GET /api/data`, `POST /api/employees`, `PUT /api/employees/<id>`, `POST /api/shifts`, `PUT /api/shifts/<id>`, `GET /api/employees.csv`, `GET /api/audit`.

Writes require JSON and `X-HR-Request: 1`. Authenticated writes also require the `X-CSRF-Token` returned by login or `/api/me`. API authorization is enforced on the server. Updates require the record's `version` field; stale edits return 409. There is no public registration or destructive delete API.

## Open source

Source code is provided under the [MIT License](LICENSE). You can modify, redistribute and publish this source in your own GitHub repository. Dependencies retain their own licenses. The package has not been published to GitHub on your behalf.

The interface is original, informed by user-supplied workflow screenshots. No VishvaHR backend code or branding assets are included. The company name is configurable in the HTML template; the logo is a simple original V mark.

See [SECURITY.md](SECURITY.md), [CONTRIBUTING.md](CONTRIBUTING.md) and [TESTING.md](TESTING.md).
