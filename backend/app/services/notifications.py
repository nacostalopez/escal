"""Shared "email the account's owner(s) about this store" logic, used by
both app/services/alerts.py and app/services/reports.py — extracted here
rather than duplicated since it's identical between the two: look up
recipients, send, log-and-swallow a failure so one bad address doesn't
block the rest of a check/report run.
"""

import logging

from sqlalchemy.orm import Session

from app.email import send_email
from app.models import Store, User

logger = logging.getLogger("escal.notifications")


def recipients_for_store(db: Session, store: Store) -> list[str]:
    owners = db.query(User).filter_by(account_id=store.account_id, role="owner").all()
    return [u.email for u in owners]


def send_to_store(db: Session, store: Store, subject: str, body: str) -> None:
    for to in recipients_for_store(db, store):
        try:
            send_email(to, subject, body)
        except Exception:
            logger.exception("store_notification_failed", extra={"store_id": str(store.id), "to": to})
