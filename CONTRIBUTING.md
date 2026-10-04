# Contributing

Contributions are welcome under the MIT License. Use fictional data in examples and tests.

1. Open an issue describing the problem and expected behavior (after publishing your repository).
2. Keep employee and shift changes independent of payroll or attendance inference.
3. Run `python -m unittest discover -s tests -v` and `node --check static/app.js`.
4. Include a migration and backup/restore notes for any schema changes.
5. Maintain server-side authentication, CSRF, parameterized queries, output escaping and concurrency checks.

Before adding attendance processing, specify overnight boundaries, competing arrival windows, missing punches, multiple shifts per day, breaks and effective dates. Before adding payroll, obtain approved monthly/daily salary and paid/unpaid weekly-off rules and reconciliation examples.
