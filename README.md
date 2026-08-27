# Escal

E-commerce analytics backend (Triple Whale / Scalify style) — True ROAS, net profit,
and ad spend consolidation across stores. Standalone project, independent of any
other repo on this machine.

## Stack

- **FastAPI** (Python) — REST API
- **PostgreSQL + TimescaleDB** — relational config tables + hypertables for orders,
  pixel events, and ad spend, with a continuous aggregate for fast daily rollups
- **Docker Compose** — one command to run the whole stack locally

Schema lives in [`db/init/`](db/init) and matches the design: `accounts`, `stores`,
`store_credentials`, `products` as regular tables; `orders`, `pixel_events`,
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

## API overview

- `POST /accounts`, `GET /accounts`
- `POST /stores`, `GET /stores`, `PUT /stores/{id}/credentials` (OAuth tokens per provider)
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

This is the functional core: schema + ingestion + the profit/ROAS math. Not yet built:

- Auth (no login/JWT yet — API is open, for local dev only)
- Encryption at rest for `store_credentials.access_token`
- Real platform connectors (Shopify/Tiendanube webhooks, Meta/Google Ads API pulls,
  MercadoPago) — right now data comes in via the bulk ingest endpoints
- Frontend dashboard
- Multi-tenant auth/permissions per account

Design/UI is intentionally deferred — this is the "make it useful" pass.
