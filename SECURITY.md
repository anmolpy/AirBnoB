# Deployment safeguards

Production selection is validated using the application's resolved configuration, including `create_app("production")`. Unknown configuration names fail closed. Production requires a non-default JWT secret of at least 32 characters and refuses debug mode. Generate a random secret in your deployment's secret manager; do not commit it.

The two committed SQLite databases were confirmed by the owner to contain synthetic, never-reused data. They are removed and local database files are ignored. Existing migrations/models and synthetic pytest fixtures remain; no live account resets are required for these sample records. Old Git history still includes the samples.

Guest status access expires after the booked checkout date even if scheduled cleanup has not run. Pre-arrival status access remains available.

Run backend tests from the repository root with `PYTHONPATH=backend python -m pytest tests` after installing `backend/requirements.txt`.
