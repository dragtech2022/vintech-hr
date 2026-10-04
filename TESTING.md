# v0.3.0 verification

## Executed successfully

- `python -m unittest discover -s tests -v`: 15 tests passed (8 existing + 7 company tests).
- Company tests start with a v0.2.0 database and verify additive initialization,
  retained administrator/employee records and idempotent initialization.
- All company settings round trip, duplicate codes, validation and stale-update conflict handling.
- Authenticated file access, CSRF/origin rejection, document uploads/metadata edits,
  archive/version checks, company/document boundaries and file validation.
- Logo replacement, PDF rejection for logos, database backup integrity and retained file bytes.
- `node --check static/app.js` and `node --check static/company.js` passed.
- `bash -n scripts/update-from-github.sh` passed.
- `tests/ui_smoke.cjs` passed using jsdom against a real local Flask server with a
  temporary database: login, five tabs, company creation/settings persistence,
  document upload/edit, company editing, employee/shift navigation and logout.
  Native dialogs were shimmed; this is a DOM/HTTP test, not a rendered-browser test.

Run backend tests in a virtualenv with `pip install -r requirements.txt`.
The optional DOM test needs Node.js with `jsdom` installed and a disposable local
app at `HR_TEST_URL` (default http://127.0.0.1:18089/), using test administrator
`admin` / `test-password-123`. **Never run it against production:** it creates
sample records. Use a separate temporary database; these credentials are test
fixtures only and are not shipped as an application account.

## Not verified in this environment

Docker is unavailable. The Docker image build and actual GitHub upgrade/rollback
script have not been executed here. The script performs its own preflight,
backup and application health verification when run on Hyper.

Playwright Chromium installation failed because the browser download was
unavailable/truncated. No rendered-browser layout or native browser-cookie test
was completed for v0.3.0. The deployed HTTPS/cookie path must be checked on Hyper.

## Server acceptance

1. Confirm `/healthz` reports v0.3.0 over HTTPS with no certificate warning.
2. Sign in with an existing account. Verify previous employees and shifts.
3. Create a test company; save and reopen each settings tab.
4. Upload/reopen a small logo and PDF, edit metadata, and archive the test file.
5. Confirm a signed-out browser cannot download a company document.
6. Verify the update backup folder and keep a copy on another disk.
