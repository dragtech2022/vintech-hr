# Security

This first release is an admin-only, single-company application. All accounts created through the local administration command have full access. It must not be treated as a multi-tenant or employee self-service system.

- Use HTTPS for network access. Default loopback access is intended for an SSH tunnel.
- Create long, unique administrator passwords. No credentials are distributed.
- Browser code cannot read the session cookie; sessions are stored hashed in the database and revoked on logout/password reset.
- Every API record operation requires a current authenticated session. Writes require same-origin custom headers and an authenticated CSRF token.
- Parameterized SQL and escaped browser rendering are used. CSV values are protected against common spreadsheet formula injection.
- Login throttling uses username and direct-peer IP buckets. Behind a reverse proxy, clients share the proxy's IP bucket; add per-client throttling at the trusted proxy if needed. No forwarded client-IP headers are blindly trusted.
- Protect the Docker host and backups. SQLite and its backups are not encrypted by the application; use encrypted storage where required.
- Do not commit employee data, `.env`, database files, screenshots with personal information or backups.
- The login shell is public, but records are authenticated. No public registration is available.
- Keep base images and dependencies reviewed and patched. Pins make this release reproducible; they are not a promise of perpetual security support.
- If you find a vulnerability, report it privately to your deployment administrator. Do not post passwords or employee information in a public issue.

There has been no independent penetration test. Do not expose the service directly on public HTTP.
