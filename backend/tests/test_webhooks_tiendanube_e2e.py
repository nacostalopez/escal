"""End-to-end tests for the Tiendanube webhook endpoint.

Mirrors test_webhooks_e2e.py's Shopify coverage: signature validation, order
ingestion/upsert, tiendanube_webhooks_log auditing, and connector_status all
have to line up together through the real route against a live test database.
"""
import base64
import hashlib
import hmac
import json
from uuid import uuid4

import pytest

from app.models import ConnectorStatus, Store, TiendanubeWebhookLog
from app.models.hypertables import orders as orders_table

TIENDANUBE_SECRET = "test-tiendanube-webhook-secret"


def _sign(body: str, secret: str = TIENDANUBE_SECRET) -> str:
    digest = hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _order_payload(order_id: int, total: str = "49.99") -> dict:
    return {
        "id": order_id,
        "total": total,
        "discount": "0.00",
        "shipping_cost_customer": "5.00",
        "created_at": "2026-02-01T12:00:00Z",
        "currency": "USD",
        "landing_url": "https://mystore.com/?utm_source=meta&utm_campaign=demo&utm_medium=cpc&utm_content=v2&gclid=g456",
    }


@pytest.fixture(autouse=True)
def tiendanube_secret_env(monkeypatch):
    # TiendanubeSettings reads TIENDANUBE_CLIENT_SECRET at connector-construction
    # time, so the signature we compute here must be made with the same value.
    monkeypatch.setenv("TIENDANUBE_CLIENT_SECRET", TIENDANUBE_SECRET)


@pytest.fixture
def tiendanube_store(test_db_session, test_account):
    """A store on the Tiendanube platform (test_store defaults to shopify)."""
    store = Store(
        id=uuid4(),
        account_id=test_account.id,
        name="Tiendanube Test Store",
        platform="tiendanube",
        currency="USD",
        timezone="UTC",
    )
    test_db_session.add(store)
    test_db_session.commit()
    test_db_session.refresh(store)
    return store


@pytest.mark.db
@pytest.mark.webhook
class TestTiendanubeWebhookEndToEnd:
    def test_valid_order_webhook_ingests_order_and_logs(self, client, test_db_session, tiendanube_store):
        body = json.dumps(_order_payload(655001))

        response = client.post(
            f"/connectors/tiendanube/webhook/{tiendanube_store.id}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Linkedstore-Hmac-Sha256": _sign(body),
                "X-Linkedstore-Topic": "order/created",
            },
        )

        assert response.status_code == 200
        assert response.json() == {"status": "received"}

        row = test_db_session.execute(
            orders_table.select().where(orders_table.c.order_id == "655001")
        ).first()
        assert row is not None
        assert float(row.gross_amount) == 49.99
        assert row.attribution_utm_source == "meta"
        assert row.utm_medium == "cpc"
        assert row.utm_content == "v2"
        assert row.click_id == "g:g456"
        assert row.landing_url == _order_payload(655001)["landing_url"]

        log = test_db_session.query(TiendanubeWebhookLog).filter_by(store_id=tiendanube_store.id).one()
        assert log.status == "processed"
        assert log.signature_valid is True

        status_row = test_db_session.query(ConnectorStatus).filter_by(
            store_id=tiendanube_store.id, provider="tiendanube",
        ).one()
        assert status_row.last_success_at is not None
        assert status_row.last_error is None

    def test_invalid_signature_is_rejected_and_logged(self, client, test_db_session, tiendanube_store):
        body = json.dumps(_order_payload(655002))

        response = client.post(
            f"/connectors/tiendanube/webhook/{tiendanube_store.id}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Linkedstore-Hmac-Sha256": "not-a-real-signature",
                "X-Linkedstore-Topic": "order/created",
            },
        )

        assert response.status_code == 401

        log = test_db_session.query(TiendanubeWebhookLog).filter_by(store_id=tiendanube_store.id).one()
        assert log.status == "rejected"
        assert log.signature_valid is False

        status_row = test_db_session.query(ConnectorStatus).filter_by(
            store_id=tiendanube_store.id, provider="tiendanube",
        ).one()
        assert status_row.last_error == "Invalid webhook signature"

        assert test_db_session.execute(
            orders_table.select().where(orders_table.c.order_id == "655002")
        ).first() is None

    def test_unknown_store_returns_404(self, client):
        body = json.dumps(_order_payload(655003))

        response = client.post(
            f"/connectors/tiendanube/webhook/{uuid4()}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Linkedstore-Hmac-Sha256": _sign(body),
                "X-Linkedstore-Topic": "order/created",
            },
        )

        assert response.status_code == 404

    def test_processing_error_is_logged_and_leaves_no_order(self, client, test_db_session, tiendanube_store):
        body = json.dumps({"id": 655004, "total": "not-a-number", "created_at": "2026-02-01T12:00:00Z"})

        response = client.post(
            f"/connectors/tiendanube/webhook/{tiendanube_store.id}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Linkedstore-Hmac-Sha256": _sign(body),
                "X-Linkedstore-Topic": "order/created",
            },
        )

        assert response.status_code == 400

        log = test_db_session.query(TiendanubeWebhookLog).filter_by(
            store_id=tiendanube_store.id, status="error",
        ).one()
        assert log.signature_valid is True
        assert log.error_message

        status_row = test_db_session.query(ConnectorStatus).filter_by(
            store_id=tiendanube_store.id, provider="tiendanube",
        ).one()
        assert status_row.last_error

        assert test_db_session.execute(
            orders_table.select().where(orders_table.c.order_id == "655004")
        ).first() is None
