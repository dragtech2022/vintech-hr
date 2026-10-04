# Validation — 0.2.0

Verified in the build environment (Python 3.12):

- Eight isolated backend tests passed: authenticated data access, CSRF/custom-header and cross-origin rejection, logout revocation, cookie flags, login throttling, employee/shift persistence, duplicate codes, stale-edit rejection, overnight validation, minimum-hours validation, three-shift limit, reference checks, CSV escaping, date validation, health response and response security headers.
- Live Gunicorn with two workers: HTTP health check, login and authenticated data read passed against a disposable database.
- SQLite backup command and streamed backup helper passed integrity and read-back checks.
- JavaScript syntax and shell script syntax checks passed.
- No live employee records were used in tests or embedded in this package.

Not verified:

- Interactive browser/rendering QA: the available browser package could not download a working Chromium executable. Interface source has been checked but browser interactions and responsive rendering require a local smoke test.
- Docker image build or Compose execution: Docker is unavailable in the build environment.
- Your Ubuntu host, reverse proxy, TLS, network or biometric devices.
- Payroll, attendance processing or statutory compliance: these are outside this release.

## First-server acceptance check

1. Build and start using INSTALL-UBUNTU.md; confirm health.
2. Create the administrator and sign in through the SSH tunnel.
3. Add a test day shift and test overnight shift. Check Next day behavior.
4. Add a fictional employee, assign both shifts, save, refresh and reopen it.
5. Edit the name/pay basis, check search/status filters, export CSV and check Activity log.
6. Open the same record in two tabs; save one, then save the old version in the other. Expect a conflict message and reload before editing.
7. Sign out, then verify that data cannot be retrieved without login.
8. Restart the app and confirm records persist. Run the backup script and retain its output securely.
9. Mark the fictional test employee inactive and remove test shift assignments before making the test shifts inactive.
10. Verify phone-size layout and keyboard operation before entering real employee data.
