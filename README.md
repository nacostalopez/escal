# ARAMAL

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

Every endpoint except `POST /auth/register`, `POST /auth/login`, and
`POST /accounts/invites/accept` requires a JWT bearer token. Accounts support
multiple users, each with one of three roles:

- **owner** — full access, plus inviting/removing members and changing roles
- **admin** — can read and write stores/products/orders/connectors, but can't manage members
- **viewer** — read-only

Registering creates a brand-new account with the registering user as its
`owner`. Additional members join via an invite, never via `/auth/register`
again (an email can only belong to one account):

```bash
curl -X POST localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"account_name": "My Store", "email": "me@example.com", "password": "at-least-8-chars"}'
# => {"access_token": "...", "refresh_token": "...", "token_type": "bearer"}

curl localhost:8000/stores -H "Authorization: Bearer <access_token>"

# Owner invites a teammate — this also emails them an accept link (see
# "Email" below; with no SMTP configured it just logs instead of sending):
curl -X POST localhost:8000/accounts/invites \
  -H "Authorization: Bearer <owner_access_token>" \
  -H "Content-Type: application/json" \
  -d '{"email": "teammate@example.com", "role": "viewer"}'
# => {"id": "...", "token": "...", ...}  — token is only ever shown here (fallback if email delivery fails)

# Invitee accepts (no auth required — they have no account yet):
curl -X POST localhost:8000/accounts/invites/accept \
  -H "Content-Type: application/json" \
  -d '{"token": "<token from above>", "password": "at-least-8-chars"}'
# => {"access_token": "...", "refresh_token": "...", "token_type": "bearer"}
```

### Password reset

```bash
# Always returns the same generic message, whether or not the email is
# registered, so the response can't be used to enumerate accounts. With no
# SMTP configured, the reset link/token is logged instead of emailed.
curl -X POST localhost:8000/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{"email": "me@example.com"}'
# => {"message": "If that email is registered, we've sent a password reset link."}

curl -X POST localhost:8000/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{"token": "<token from the email>", "password": "at-least-8-chars"}'
# => {"access_token": "...", "refresh_token": "...", "token_type": "bearer"}
# The token is single-use and expires after 60 minutes; on success every
# existing refresh token for the account is revoked (other devices stay
# logged in only until their access token naturally expires) and the caller
# is logged back in with a fresh token pair.
```

Role is read fresh from the database on every request (not baked into the
JWT), so a role change or member removal takes effect on the very next
request rather than waiting out the access token's lifetime.

### Refresh tokens

Access tokens are short-lived (`ACCESS_TOKEN_EXPIRE_MINUTES`, default 15
min); a separate opaque refresh token (`REFRESH_TOKEN_EXPIRE_DAYS`, default
30 days) is issued alongside it by every endpoint above and persisted
(hashed, like invite tokens) in `refresh_tokens`:

```bash
curl -X POST localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "<refresh_token>"}'
# => new {"access_token": "...", "refresh_token": "..."} — the old refresh
#    token is revoked in the same request (rotation), so reusing it 401s

curl -X POST localhost:8000/auth/logout \
  -H "Authorization: Bearer <access_token>" -H "Content-Type: application/json" \
  -d '{"refresh_token": "<refresh_token>"}'
# revokes just that one refresh token (this device/session)
```

The frontend (`frontend/`) stores both tokens and transparently refreshes:
any `401` from the API triggers one `/auth/refresh` call (concurrent 401s
share a single in-flight refresh so the token isn't rotated twice), then
retries the original request — so a session survives past the 15-minute
access token lifetime without re-prompting for login, until the refresh
token itself expires or is revoked.

Every `/stores/{id}/...` route checks that the store belongs to the caller's
account (404, not 403, on mismatch — no confirming another account's store
exists). `store_credentials.access_token`/`refresh_token` are encrypted at
rest with Fernet (`CREDENTIALS_ENCRYPTION_KEY`) before they hit the database.

Set `JWT_SECRET` and `CREDENTIALS_ENCRYPTION_KEY` in `.env` for anything
beyond local dev — see `.env.example`.

### Dashboard layout

The summary board's widgets — which ones show, their order, and which stat
is the 2x2 hero tile — are a per-user preference (`dashboard_layouts`, one
row per user), not per-account or per-store: each teammate arranges their
own view of the same underlying data. A user with no saved layout gets a
sensible default (every widget, True ROAS as hero) rather than an empty
board:

```bash
curl localhost:8000/dashboard/layout -H "Authorization: Bearer <access_token>"
# => {"widgets": [{"type": "stat_roas", "hero": true}, {"type": "stat_revenue", "hero": false}, ...]}

curl -X PUT localhost:8000/dashboard/layout \
  -H "Authorization: Bearer <access_token>" -H "Content-Type: application/json" \
  -d '{"widgets": [{"type": "stat_roas", "hero": true}, {"type": "chart_daily", "hero": false}]}'
# replaces the whole layout — the frontend always sends the full widget
# list after any add/remove/reorder/hero change, so this is a full
# overwrite, not a patch
```

Any role (including viewer) can save their own layout — it's a display
preference, not a data-access permission. Widget types are validated
server-side (`WidgetType` in `app/schemas/dashboard.py`); an unknown type or
a duplicate type in the same layout is rejected with `422`.

### Creative analytics

`ad_spend` tracks spend at campaign/adset level; `creative_performance` is a
separate hypertable for the ad (creative) level — what a media buyer
actually scans to decide what to scale or kill. Meta and Google only
(Tiendanube/MercadoPago aren't creative-based ad platforms). `MetaConnector`
and `GoogleAdsConnector` each get a `fetch_creative_performance()` alongside
their existing `fetch_ad_spend()`, and the connector routes get a matching
`.../sync-creative-performance` next to `.../sync-ad-spend`. Thumbnail
images aren't fetched yet — both platforms need a separate per-creative API
call to get them, deliberately left for later rather than adding N+1
requests to every sync.

`GET /stores/{id}/metrics/creatives?start=&end=` aggregates
`creative_performance` by ad, sums spend/impressions/clicks over the range,
computes CTR/CPC/CPM server-side, and ranks by spend descending — this is
what the dashboard's "Performance por creativo" widget (add it via
"Personalizar" — it's not in the default layout) renders as a table.

### Customer identity

`orders` had no concept of "customer" at all — every row was anonymous, no
email/phone, no stable id linking two orders from the same buyer. That
blocks any LTV, cohort, repeat-purchase, or CAC-payback feature, since none
of those can be built without first knowing "these two orders are the same
person." `app/services/customers.py::resolve_customer_id()` is the one
place that gets solved: every order-ingestion path (bulk
`POST /stores/{id}/orders`, Shopify webhook, Tiendanube webhook) calls it
with whatever email/phone it has, and it finds-or-creates the matching
`customers` row and returns its id to store on the order.

**Hash-only, no plaintext PII at rest** — deliberately extending the same
convention `pixel_events.user_email_hash` already established, rather than
storing anything decryptable:

- Email is normalized (trim + lowercase) and phone (digits only, no leading
  zeros) the same way Meta/Google Conversions APIs expect before SHA-256
  hashing, so `customers.email_hash`/`phone_hash` would already be
  CAPI-ready if that gets built later, with no separate re-hash needed.
- None of LTV-by-cohort, CAC payback, or product journeys need to *display*
  an actual email anywhere — a stable hash fully covers dedup.
- Storing zero reversible PII means no "right to erasure" complexity for a
  product whose merchants' end-customers never consented to Escal
  specifically.

`orders.customer_id` intentionally has **no FK constraint** to
`customers.id` (same as `orders.store_id` having none either) — `Customer`
is an ORM-managed table (gets created/dropped fresh every test session),
while `orders` is a hypertable that persists across test runs untouched;
a real FK there would make `Base.metadata.drop_all()` fail at every test
teardown once a single row existed referencing it.

This ships only the identity foundation — no LTV/cohort/CAC endpoints or
UI yet; those are a natural follow-up now that this exists (see
"Status / next steps").

## API overview

- `POST /auth/register`, `POST /auth/login`, `GET /auth/me`
- `POST /auth/refresh` (rotates a refresh token), `POST /auth/logout` (revokes one)
- `POST /auth/forgot-password` (always a generic response), `POST /auth/reset-password`
  (single-use token, revokes existing refresh tokens, logs the caller back in)
- `GET /accounts/me`, `GET /accounts/members`
- `POST /accounts/invites`, `GET /accounts/invites`, `DELETE /accounts/invites/{id}`,
  `POST /accounts/invites/{id}/resend` (fresh token + expiry, same email),
  `POST /accounts/invites/accept` — owner-only except accept
- `PATCH /accounts/members/{id}/role`, `DELETE /accounts/members/{id}` — owner-only
- `GET /dashboard/layout`, `PUT /dashboard/layout` — per-user (any role) summary
  board customization: which widgets show, their order, and which stat is the
  2x2 hero tile
- `POST /stores`, `GET /stores`, `GET /stores/{id}`,
  `PUT /stores/{id}/credentials` (OAuth tokens per provider, encrypted at rest)
- `PUT /stores/{id}/products` (bulk upsert by `external_id`, carries COGS/shipping cost)
- `POST /stores/{id}/orders` (bulk ingest/upsert, accepts optional
  `customer_email`/`customer_phone` resolved server-side to `customer_id` —
  see "Customer identity"), `GET /stores/{id}/orders?start=&end=`
- `POST /stores/{id}/pixel-events` (bulk ingest), `GET /stores/{id}/pixel-events?...`
- `POST /stores/{id}/ad-spend` (bulk ingest), `GET /stores/{id}/ad-spend?...`
- `POST /stores/{id}/creative-performance` (bulk ingest), `GET /stores/{id}/creative-performance?...`
  — ad-level (Meta/Google only), separate from `ad_spend` since it's per-ad not per-campaign
- `GET /stores/{id}/metrics/summary?start=&end=` — revenue, net profit, ad spend,
  real profit after ads, **true ROAS** (`net_profit / ad_spend` — net of discounts,
  shipping, gateway fees and COGS, not plain revenue/spend; reads live from
  `orders`, always fresh)
- `GET /stores/{id}/metrics/daily?start=&end=` — daily breakdown via the
  `daily_financial_summary` continuous aggregate (fast, but can lag up to ~1h
  behind since it refreshes on an hourly policy — see `db/init/004_continuous_aggregates.sql`)
- `GET /stores/{id}/metrics/creatives?start=&end=` — one row per ad, summed
  over the range and ranked by spend, with CTR/CPC/CPM computed server-side
  (see "Creative analytics" below)
- `GET/POST /connectors/{shopify,meta,google,tiendanube,mercadopago}/...` —
  OAuth handshake, ad-spend sync, and (Shopify/Tiendanube) order webhook per
  provider; Meta/Google also get `.../sync-creative-performance` — see `DEVELOPMENT.md`
- `GET /stores/{id}/connectors/health` — per-provider sync status

All requests are logged as structured JSON (see `DEVELOPMENT.md`) and rate
limited (200/min default, tighter on `/auth/*` and the Shopify webhook) —
exceeding a limit returns `429`.

## Status / next steps

Schema, ingestion, profit/ROAS math, auth/credential-encryption,
Shopify/Meta/Google/Tiendanube/MercadoPago connectors, CI, structured
logging, rate limiting, env-var validation, webhook e2e tests, multi-user
accounts with Owner/Admin/Viewer roles, revocable refresh tokens, invite and
password-reset emails (via SMTP, configurable through env vars), transparent
frontend token refresh, and hash-only customer identity resolution (every
order-ingestion path links to a deduplicated, PII-free `customers` row —
see "Customer identity") are done.

The frontend (`frontend/`, plain HTML/CSS/JS, no build step) has been carried
well past "just enough to see real numbers": ARAMAL brand system with light/
dark mode, a Spanish (`vos`-register, es-AR-formatted) UI throughout, a
user-configurable summary board (add/remove/reorder widgets, pick which stat
is the 2x2 hero, plus an opt-in creative-analytics table ranked by spend —
see "Dashboard layout" and "Creative analytics" below) with real
period-over-period deltas, hover tooltips on the daily revenue-vs-spend
chart, a full Equipo (team) screen for the invite/role/remove routes above
(including a "Reenviar" action for a pending invite), an invite-link landing
flow (`index.html?invite_token=...`), and a forgot/reset-password flow
(`index.html?reset_token=...`). Not yet built:

- No password strength meter on the frontend.
- No revenue/ROAS attribution down to the individual ad — creative
  analytics currently shows each platform's own metrics (spend, CTR, CPC,
  CPM), not net_profit or true ROAS per creative. `orders` only carries
  `attribution_utm_source`/`attribution_utm_campaign`, nothing at ad/creative
  granularity, so that would need a deeper attribution pipeline change.
- No thumbnail images in the creative-performance table (see "Creative
  analytics" below for why).
- No LTV/cohort, CAC-payback, or product-journey endpoints or UI yet —
  "Customer identity" below only ships the foundation (deduplicated
  `customers` rows linked from `orders`) those features need; building them
  is the natural next step now that it exists.
- Pre-existing, unrelated to any feature above: `MetaConnector`/
  `GoogleAdsConnector` are constructed without an `ad_account_id`/
  `customer_id` in `routes/connectors.py`'s sync routes (both `sync-ad-spend`
  and the new `sync-creative-performance`), so calling them against a real
  connected account 400s with "ad_account_id required" /
  "customer_id required" — `StoreCredential.provider_account_id` exists and
  looks like where that value belongs, but nothing threads it through yet.
  Doesn't block anything backed by direct ingestion (bulk POST, demo seed
  data) since that bypasses these sync routes entirely.
- `tests/test_auth.py::TestAuthenticatedRequests::test_get_current_user_no_token`
  expects `403` from `HTTPBearer` with no Authorization header, but the
  installed fastapi/starlette version returns `401` (pre-existing, unrelated
  to any feature above).

Note for `docker compose` users: `FRONTEND_URL` and `SMTP_*` must be set in a
root-level `.env` (not `backend/.env`) — `docker-compose.yml`'s `backend`
service only forwards env vars it explicitly lists, and a root `.env` is
what Compose itself reads for `${VAR}` substitution in that file.
