"""End-to-end tests for the Shopify webhook endpoint.

Unlike test_connectors_schema.py (mocked HTTP, no DB), these hit the real
route through TestClient against a live test database: signature
validation, order ingestion/upsert, shopify_webhooks_log auditing, and
connector_status all have to line up together, the way they do in production.
"""
import base64
import hashlib
import hmac
import json
from uuid import uuid4

import pytest

from app.models import ConnectorStatus, ShopifyWebhookLog
from app.models.hypertables import orders as orders_table

SHOPIFY_SECRET = "test-shopify-webhook-secret"


def _sign(body: str, secret: str = SHOPIFY_SECRET) -> str:
    digest = hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _order_payload(order_id: int, total_price: str = "49.99") -> dict:
    return {
        "id": order_id,
        "total_price": total_price,
        "total_discounts": "0.00",
        "shipping_lines": [{"price": "5.00"}],
        "transactions": [{"kind": "capture", "gateway_fee": "1.50"}],
        "line_items": [],
        "created_at": "2026-02-01T12:00:00Z",
        "currency": "USD",
        "note": "utm_source=meta&utm_campaign=demo&utm_medium=paid_social&utm_content=v1&fbclid=fb123",
        "landing_site": "/products/demo",
    }


@pytest.fixture(autouse=True)
def shopify_secret_env(monkeypatch):
    # ShopifySettings reads SHOPIFY_API_SECRET at connector-construction time,
    # so the signature we compute here must be made with the same value.
    monkeypatch.setenv("SHOPIFY_API_SECRET", SHOPIFY_SECRET)


@pytest.mark.db
@pytest.mark.webhook
class TestShopifyWebhookEndToEnd:
    def test_valid_order_webhook_ingests_order_and_logs(self, client, test_db_session, test_store):
        body = json.dumps(_order_payload(555001))

        response = client.post(
            f"/connectors/shopify/webhook/{test_store.id}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Shopify-Hmac-Sha256": _sign(body),
                "X-Shopify-Topic": "orders/create",
            },
        )

        assert response.status_code == 200
        assert response.json() == {"status": "received"}

        row = test_db_session.execute(
            orders_table.select().where(orders_table.c.order_id == "555001")
        ).first()
        assert row is not None
        assert float(row.gross_amount) == 49.99
        assert row.attribution_utm_source == "meta"
        assert row.utm_medium == "paid_social"
        assert row.utm_content == "v1"
        assert row.click_id == "fb:fb123"
        assert row.landing_url == "/products/demo"

        log = test_db_session.query(ShopifyWebhookLog).filter_by(store_id=test_store.id).one()
        assert log.status == "processed"
        assert log.signature_valid is True

        status_row = test_db_session.query(ConnectorStatus).filter_by(
            store_id=test_store.id, provider="shopify",
        ).one()
        assert status_row.last_success_at is not None
        assert status_row.last_error is None

    def test_invalid_signature_is_rejected_and_logged(self, client, test_db_session, test_store):
        body = json.dumps(_order_payload(555002))

        response = client.post(
            f"/connectors/shopify/webhook/{test_store.id}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Shopify-Hmac-Sha256": "not-a-real-signature",
                "X-Shopify-Topic": "orders/create",
            },
        )

        assert response.status_code == 401

        log = test_db_session.query(ShopifyWebhookLog).filter_by(store_id=test_store.id).one()
        assert log.status == "rejected"
        assert log.signature_valid is False

        status_row = test_db_session.query(ConnectorStatus).filter_by(
            store_id=test_store.id, provider="shopify",
        ).one()
        assert status_row.last_error == "Invalid webhook signature"

        assert test_db_session.execute(
            orders_table.select().where(orders_table.c.order_id == "555002")
        ).first() is None

    def test_duplicate_order_webhook_upserts_instead_of_duplicating(self, client, test_db_session, test_store):
        headers = {"Content-Type": "application/json", "X-Shopify-Topic": "orders/create"}

        first_body = json.dumps(_order_payload(555003, total_price="10.00"))
        first = client.post(
            f"/connectors/shopify/webhook/{test_store.id}",
            content=first_body,
            headers={**headers, "X-Shopify-Hmac-Sha256": _sign(first_body)},
        )
        assert first.status_code == 200

        second_body = json.dumps(_order_payload(555003, total_price="25.00"))
        second = client.post(
            f"/connectors/shopify/webhook/{test_store.id}",
            content=second_body,
            headers={
                **headers,
                "X-Shopify-Hmac-Sha256": _sign(second_body),
                "X-Shopify-Topic": "orders/updated",
            },
        )
        assert second.status_code == 200

        rows = test_db_session.execute(
            orders_table.select().where(orders_table.c.order_id == "555003")
        ).all()
        assert len(rows) == 1
        assert float(rows[0].gross_amount) == 25.00

    def test_unknown_store_returns_404(self, client):
        body = json.dumps(_order_payload(555004))

        response = client.post(
            f"/connectors/shopify/webhook/{uuid4()}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Shopify-Hmac-Sha256": _sign(body),
                "X-Shopify-Topic": "orders/create",
            },
        )

        assert response.status_code == 404

    def test_processing_error_is_logged_and_leaves_no_order(self, client, test_db_session, test_store):
        # Not a valid number -> float() raises inside _process_order_webhook,
        # which the route must catch, log, and report as a clean 400.
        body = json.dumps({"id": 555005, "total_price": "not-a-number", "created_at": "2026-02-01T12:00:00Z"})

        response = client.post(
            f"/connectors/shopify/webhook/{test_store.id}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Shopify-Hmac-Sha256": _sign(body),
                "X-Shopify-Topic": "orders/create",
            },
        )

        assert response.status_code == 400

        log = test_db_session.query(ShopifyWebhookLog).filter_by(
            store_id=test_store.id, status="error",
        ).one()
        assert log.signature_valid is True
        assert log.error_message

        status_row = test_db_session.query(ConnectorStatus).filter_by(
            store_id=test_store.id, provider="shopify",
        ).one()
        assert status_row.last_error

        assert test_db_session.execute(
            orders_table.select().where(orders_table.c.order_id == "555005")
        ).first() is None
