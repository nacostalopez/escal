# Security notes

## Credential rotation schedule

| Secret | Rotate | Notes |
|---|---|---|
| `JWT_SECRET` | Annually, or immediately if leaked | Rotating invalidates every existing session (7-day tokens, no refresh/revocation yet — see README "Status / next steps"). |
| `CREDENTIALS_ENCRYPTION_KEY` | Only if leaked | Rotating this **without** re-encrypting existing `store_credentials` rows makes them permanently unreadable (Fernet decrypt fails). If rotation is ever needed: decrypt all rows with the old key, re-encrypt with the new one, in the same transaction as the key swap. `scripts/audit_ownership.py` will flag any row that fails to decrypt with the current key. |
| Shopify API key/secret | Annually | Shopify access tokens themselves don't expire. |
| Meta app secret | Annually, or if compromised | Meta access tokens don't expire for business accounts. |
| Google OAuth client secret | Annually | Independent of the per-store refresh token below. |
| Google Ads developer token | Per Google's own policy | Not something this app controls the lifecycle of. |
| Per-store refresh tokens (Google) | Auto-handled | Access tokens expire hourly; `sync_google_ad_spend` refreshes automatically and logs the attempt to `token_refresh_audit`. |

## Encryption at rest

`store_credentials.access_token` / `refresh_token` are Fernet-encrypted (`app/security.py`) before they ever reach the database — see `encrypt_secret` / `decrypt_secret`. Run `scripts/audit_ownership.py` periodically to catch rows that no longer decrypt (rotated key without re-encryption, or corrupted data) and rows that reference a deleted store.

## Ownership isolation

Every `/stores/{id}/...` route (including connector OAuth/webhook/sync endpoints) verifies `store.account_id == current_user.account_id` before returning anything — a mismatch is a plain 404, not a 403, so error responses never confirm that a store exists in another account. See `app/dependencies.py::get_owned_store`.

## Reporting

Single-developer project at the moment — no formal disclosure process yet. If that changes, add contact details here.
