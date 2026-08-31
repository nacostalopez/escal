# Escal

E-commerce analytics backend (Triple Whale / Scalify style) — True ROAS, net profit,
and ad spend consolidation across stores. Standalone project, independent of any
other repo on this machine.

## Stack

- **FastAPI** (Python) — REST API
- **PostgreSQL + TimescaleDB** — relational config tables + hypertables for orders,
  pixel events, and ad spend, with a continuous aggregate for fast daily rollups
- **Docker Compose** — one command to run the whole stack locally

Schema lives in [`db/init/`](db/init) and matches the design: `accounts`, `users`,
`stores`, `store_credentials`, `products` as regular tables; `orders`, `pixel_events`,
`ad_spend` as hypertables; `daily_financial_summary` as a continuous aggregate.

## Quickstart

```bash
docker compose up --build
```

This starts Postgres/Timescale on `localhost:5432` and the API on
`http://localhost:8000` (docs at `http://localhost:8000/docs`). The schema is
created automatically from `db/init/*.sql` on first boot.

Seed it with demo data and see a real True ROAS number:

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

## Status / next steps

Schema + ingestion + profit/ROAS math + auth/credential-encryption are done.
Not yet built:

- Real platform connectors (Shopify/Tiendanube webhooks, Meta/Google Ads API pulls,
  MercadoPago) — right now data comes in via the bulk ingest endpoints
- Frontend dashboard
- Multi-user accounts / role-based permissions (currently one user = one account)
- Refresh tokens (JWTs are long-lived, 7 days, with no revocation yet)

Design/UI is intentionally deferred — this is the "make it useful" pass.
