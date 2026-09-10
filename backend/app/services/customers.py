"""Customer identity resolution — the one place email/phone hashing lives.

Every order-ingestion path (bulk API, Shopify webhook, Tiendanube webhook)
calls resolve_customer_id() instead of hashing/upserting customers itself.
"""

import hashlib
import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Customer


def _hash_email(email: str) -> str:
    """Meta/Google Conversions API recipe: trim + lowercase, then SHA-256.
    Using their exact normalization means this hash is already CAPI-ready
    if that feature gets built later — no separate re-hash needed."""
    normalized = email.strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()


def _hash_phone(phone: str) -> str:
    """Meta/Google recipe: digits only, country code included, no leading
    zeros. Best-effort here — we don't have a phone-parsing library to
    reliably infer a missing country code from a bare local number, so this
    just strips non-digits and leading zeros from whatever the platform
    sends (Shopify/Tiendanube both send phone with a leading + and country
    code when they have it)."""
    digits = re.sub(r"\D", "", phone).lstrip("0")
    return hashlib.sha256(digits.encode()).hexdigest()


def resolve_customer_id(
    db: Session,
    store_id: UUID,
    email: str | None,
    phone: str | None,
    external_customer_id: str | None = None,
) -> UUID | None:
    """Find-or-create the Customer for this store matching the given
    email/phone, and return its id. Returns None if neither is given — the
    order simply has no linked customer, same as before this existed.

    Email is the primary dedup key; phone is only used to match when no
    email is present (a customer could plausibly share a phone with someone
    else in edge cases, but not an email).
    """
    email_hash = _hash_email(email) if email else None
    phone_hash = _hash_phone(phone) if phone else None

    if not email_hash and not phone_hash:
        return None

    existing = None
    if email_hash:
        existing = db.query(Customer).filter_by(store_id=store_id, email_hash=email_hash).first()
    elif phone_hash:
        existing = db.query(Customer).filter_by(store_id=store_id, phone_hash=phone_hash).first()

    if existing:
        # Enrich with anything new we learned about this customer, but
        # never overwrite an already-known value.
        if phone_hash and not existing.phone_hash:
            existing.phone_hash = phone_hash
        if external_customer_id and not existing.external_customer_id:
            existing.external_customer_id = external_customer_id
        return existing.id

    customer = Customer(
        store_id=store_id,
        email_hash=email_hash,
        phone_hash=phone_hash,
        external_customer_id=external_customer_id,
        first_order_at=datetime.now(timezone.utc),
    )
    db.add(customer)
    db.flush()  # populate customer.id without requiring a separate commit
    return customer.id
