# Escal

E-commerce analytics backend (Triple Whale / Scalify style) — True ROAS, net profit,
and ad spend consolidation across stores. Standalone project, independent of any
other repo on this machine.

## Stack

- **FastAPI** (Python) — REST API, plus Shopify/Meta/Google Ads connectors
  (`backend/app/connectors/`)
- **PostgreSQL + TimescaleDB** — relational config tables + hypertables for orders,
  pixel events, and ad spend, with a continuous aggregate for fast daily rollups
- **Plain HTML/CSS/JS frontend** (`frontend/`) — no build step, calls the API
  directly; served by nginx in Docker Compose
- **Docker Compose** — one command to run the whole stack locally

Schema lives in [`db/init/`](db/init) and matches the design: `accounts`, `users`,
`stores`, `store_credentials`, `products` as regular tables; `orders`, `pixel_events`,
`ad_spend` as hypertables; `daily_financial_summary` as a continuous aggregate.

## Quickstart

```bash
docker compose up --build
```

This starts Postgres/Timescale on `localhost:5432`, the API on
`http://localhost:8000` (docs at `http://localhost:8000/docs`), and the
frontend on `http://localhost:3000`. The schema is created automatically
from `db/init/*.sql` on first boot.

Open `http://localhost:3000`, register an account, create a store, and click
"Seed demo data" to see a real True ROAS number without touching the
terminal — or do the same thing from the command line:

```bash
pip install requests
python scripts/seed_demo.py
```

## Auth

Every endpoint except `POST /auth/register` and `POST /auth/login` requires a
JWT bearer token. An account is created implicitly on register — one user
owns one account for now (team members/multi-user accounts are a later step).

```bash
curl -X POST localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"account_name": "My Store", "email": "me@example.com", "password": "at-least-8-chars"}'
# => {"access_token": "...", "token_type": "bearer"}

curl localhost:8000/stores -H "Authorization: Bearer <access_token>"
```

Every `/stores/{id}/...` route checks that the store belongs to the caller's
account (404, not 403, on mismatch — no confirming another account's store
exists). `store_credentials.access_token`/`refresh_token` are encrypted at
rest with Fernet (`CREDENTIALS_ENCRYPTION_KEY`) before they hit the database.

Set `JWT_SECRET` and `CREDENTIALS_ENCRYPTION_KEY` in `.env` for anything
beyond local dev — see `.env.example`.

## API overview

- `POST /auth/register`, `POST /auth/login`, `GET /auth/me`
- `GET /accounts/me`
- `POST /stores`, `GET /stores`, `GET /stores/{id}`,
  `PUT /stores/{id}/credentials` (OAuth tokens per provider, encrypted at rest)
- `PUT /stores/{id}/products` (bulk upsert by `external_id`, carries COGS/shipping cost)
- `POST /stores/{id}/orders` (bulk ingest/upsert), `GET /stores/{id}/orders?start=&end=`
- `POST /stores/{id}/pixel-events` (bulk ingest), `GET /stores/{id}/pixel-events?...`
- `POST /stores/{id}/ad-spend` (bulk ingest), `GET /stores/{id}/ad-spend?...`
- `GET /stores/{id}/metrics/summary?start=&end=` — revenue, net profit, ad spend,
  real profit after ads, **true ROAS** (reads live from `orders`, always fresh)
- `GET /stores/{id}/metrics/daily?start=&end=` — daily breakdown via the
  `daily_financial_summary` continuous aggregate (fast, but can lag up to ~1h
  behind since it refreshes on an hourly policy — see `db/init/004_continuous_aggregates.sql`)
- `GET/POST /connectors/{shopify,meta,google}/...` — OAuth handshake, ad-spend
  sync, and (Shopify) order webhook per provider — see `DEVELOPMENT.md`
- `GET /stores/{id}/connectors/health` — per-provider sync status

All requests are logged as structured JSON (see `DEVELOPMENT.md`) and rate
limited (200/min default, tighter on `/auth/*` and the Shopify webhook) —
exceeding a limit returns `429`.

## Status / next steps

Schema, ingestion, profit/ROAS math, auth/credential-encryption, Shopify/Meta/Google
connectors, CI, a first frontend, structured logging, rate limiting, env-var
validation, and Shopify webhook e2e tests are done. Not yet built:

- Tiendanube and MercadoPago connectors (same pattern as the existing three)
- Multi-user accounts / role-based permissions (currently one user = one account)
- Refresh tokens (JWTs are long-lived, 7 days, with no revocation yet)
- The frontend is intentionally minimal (`frontend/`, no build step) — fine
  for seeing real numbers locally, not meant as a finished product design
