## Connector changes checklist
_(delete this section if the PR doesn't touch a connector)_
- [ ] Implements all `BaseConnector` abstract methods
- [ ] OAuth endpoints added in `backend/app/routes/connectors.py`
- [ ] Tokens are encrypted with Fernet (`encrypt_secret`) before hitting the DB
- [ ] Webhook signatures are validated (if the provider sends webhooks)
- [ ] `.env.example` (both root and `backend/`) updated with any new settings
- [ ] `DEVELOPMENT.md` "Adding a New Connector" section followed/updated
- [ ] Tests added in `backend/tests/test_connectors_*.py`
- [ ] No API keys or tokens appear in logs, error messages, or test fixtures

## Database changes
_(delete this section if the PR doesn't touch `db/init/`)_
- [ ] New migration file added in `db/init/`, numbered after the last existing one
- [ ] Migration tested locally (`docker compose up test-db -d` + apply it)
- [ ] Corresponding SQLAlchemy model added/updated if the app reads/writes the table

## General
- [ ] `pytest` passes locally (`cd backend && pytest`, needs `docker compose up test-db -d`)
- [ ] `ruff check backend/` passes
