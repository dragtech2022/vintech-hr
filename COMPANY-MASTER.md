# Company Master — Community v0.3.0

An independent Company Master for the existing MIT-licensed Flask/SQLite HRMS.
No Frappe dependency. Existing accounts, employees, shifts, sessions and `.env`
are retained. No real company records, bank information, statutory numbers,
contacts or screenshot files are seeded or bundled in this release.

## Included

- Searchable company list with unique company number/code, repeatable short name,
  legal name, branch/location, city and active/inactive status.
- Create/edit with server validation, optimistic version checks and activity log.
- Five editor tabs: Company details; PF/ESI/PT/IT; Allowance details;
  Other details; Documents.
- Identity, contact/address, contractor/unit/site, bank and SMTP configuration fields.
- PF and ESI registration/settings, PT, PAN/TAN, income tax settings,
  overtime and bonus settings. Rates start blank and are not legal recommendations.
- Ten allowance heads with short ID/full name/import flag; six deduction heads;
  six employer CTC heads; twelve reimbursement heads; two owner/contact sections.
- Visible other-details fields: selfie admin, mispunch application day limit,
  manager and backend contacts.
- Authenticated PDF/PNG/JPEG uploads up to 4 MiB, document metadata edit,
  expiry/reminder date indicators, downloads and soft archiving.
- Company logo and HR policy uploads via Documents. Replacing either archives
  its prior active file. Logo appears in the company list.
- All file bytes stay in SQLite and are included in the existing verified backup.
- Eight-character administrator password minimum, as requested. Existing
  passwords and password hashes are not changed.

## Scope and limitations

This release saves master records and configuration. It does not calculate
payroll, PF/ESI/PT/IT, overtime, bonus or attendance. It does not send email,
notifications, import salary heads or enforce employee application limits.
SMTP uses a future password-environment-variable reference, not a password
field; no secret is stored in the company record. No email sender is connected.

Employees and shifts remain workspace-wide; saving a company does not silently
reassign or isolate them. All current administrators can access all companies.
An authority-group label on a document is metadata, not an access permission.
No automatic copying to all units/sites is performed. A company/unit hierarchy
and propagation rules require a later module. Fields hidden above the screenshot
crop are not guessed. State, PF office, establishment type, bank and authority
labels are text fields until their own master modules exist.

Archive preserves file bytes in the database but removes the file from active
lists/downloads. There is no permanent delete or archive-restoration UI yet.
Files are type/size checked; there is no malware scanner. Documents download as
attachments; only authenticated PNG/JPEG company logos display inline.

## Publish source to GitHub first (Windows browser)

1. Extract the v0.3.0 ZIP.
2. Open https://github.com/dragtech2022/vintech-hr .
3. Add file → Upload files. Upload **all contents** of `vintech-hr-standalone`,
   preserving `scripts`, `static`, `templates`, and `tests` folders. Do not upload
   the outer folder or ZIP. Include the dotfiles for a complete release.
4. Commit as `Company Master v0.3.0`.
5. Confirm `company.py`, `static/company.js`, `COMPANY-MASTER.md` and
   `scripts/update-from-github.sh` exist in the correct locations.

## Upgrade on Hyper only (`hyper@hyper`, 192.168.2.86)

Download the update script after committing the release:

```bash
curl --fail --show-error --location https://raw.githubusercontent.com/dragtech2022/vintech-hr/main/scripts/update-from-github.sh -o /tmp/vintech-hr-update.sh
```

Run it:

```bash
bash /tmp/vintech-hr-update.sh /home/hyper/vintech-hr
```

The script fetches `origin/main`, checks for v0.3.0, and stops for unknown local
source changes. The known local eight-character password edit is accepted.
It saves a private source/config backup, a verified database backup and the
previous Docker image before a fast-forward update and Docker rebuild. It does
not modify the proxy, hostname, environment file or other Docker projects.
It checks release SHA256 hashes and waits for the application health check.
The existing named `hr_data` volume is reused; no volume is removed.

Backups are under `/home/hyper/vintech-hr-update-backups/<timestamp>/`, outside
Git. The script prints a rollback command that runs the preserved image with
the same database. Database migration only adds company tables, making this
code rollback possible without discarding saved employee or company data.
If any step fails, stop and inspect its output; do not delete or restore data.
The rollback image override must be omitted when retrying the normal upgrade.

Open https://hr.dragtech.in and refresh. Company Master is the default view.
Create a company, click Save company, then use Documents for the logo/HR policy.
The `#employees` and `#shifts` routes still work.

## Verification performed

See TESTING.md. Docker is not available in the build workspace, so the real
container build and update script require verification on Hyper. Do not infer
successful server deployment from the release ZIP alone.
