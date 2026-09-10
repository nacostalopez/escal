"""Tests for customer identity resolution (app/services/customers.py)."""

import pytest
from fastapi import status

from app.models import Customer
from app.services.customers import resolve_customer_id


@pytest.mark.db
class TestResolveCustomerId:
    def test_returns_none_with_no_email_or_phone(self, test_db_session, test_store):
        result = resolve_customer_id(test_db_session, test_store.id, None, None)
        assert result is None
        assert test_db_session.query(Customer).count() == 0

    def test_creates_a_customer_from_email(self, test_db_session, test_store):
        customer_id = resolve_customer_id(test_db_session, test_store.id, "buyer@example.com", None)
        test_db_session.commit()

        assert customer_id is not None
        customer = test_db_session.get(Customer, customer_id)
        assert customer.email_hash is not None
        assert customer.phone_hash is None
        assert customer.first_order_at is not None

    def test_same_email_dedupes_to_one_customer(self, test_db_session, test_store):
        first_id = resolve_customer_id(test_db_session, test_store.id, "buyer@example.com", None)
        test_db_session.commit()
        second_id = resolve_customer_id(test_db_session, test_store.id, "buyer@example.com", None)
        test_db_session.commit()

        assert first_id == second_id
        assert test_db_session.query(Customer).filter_by(store_id=test_store.id).count() == 1

    def test_email_normalization_dedupes_case_and_whitespace(self, test_db_session, test_store):
        first_id = resolve_customer_id(test_db_session, test_store.id, "Buyer@Example.com", None)
        test_db_session.commit()
        second_id = resolve_customer_id(test_db_session, test_store.id, "  buyer@example.com  ", None)
        test_db_session.commit()

        assert first_id == second_id

    def test_same_email_in_different_stores_is_two_customers(self, test_db_session, test_store, other_account):
        from uuid import uuid4

        from app.models import Store

        other_store = Store(id=uuid4(), account_id=other_account.id, name="Other Store", platform="shopify")
        test_db_session.add(other_store)
        test_db_session.commit()

        id_in_store_one = resolve_customer_id(test_db_session, test_store.id, "shared@example.com", None)
        test_db_session.commit()
        id_in_store_two = resolve_customer_id(test_db_session, other_store.id, "shared@example.com", None)
        test_db_session.commit()

        assert id_in_store_one != id_in_store_two

    def test_phone_only_matches_by_phone_when_no_email(self, test_db_session, test_store):
        first_id = resolve_customer_id(test_db_session, test_store.id, None, "+54 9 11 1234-5678")
        test_db_session.commit()
        second_id = resolve_customer_id(test_db_session, test_store.id, None, "5491112345678")
        test_db_session.commit()

        assert first_id == second_id

    def test_enriches_existing_customer_with_phone_learned_later(self, test_db_session, test_store):
        customer_id = resolve_customer_id(test_db_session, test_store.id, "buyer@example.com", None)
        test_db_session.commit()

        resolve_customer_id(test_db_session, test_store.id, "buyer@example.com", "+5491112345678")
        test_db_session.commit()

        customer = test_db_session.get(Customer, customer_id)
        assert customer.phone_hash is not None

    def test_no_plaintext_email_or_phone_is_ever_stored(self, test_db_session, test_store):
        resolve_customer_id(test_db_session, test_store.id, "buyer@example.com", "+5491112345678")
        test_db_session.commit()

        customer = test_db_session.query(Customer).filter_by(store_id=test_store.id).first()
        columns = {c.name for c in Customer.__table__.columns}
        assert "email" not in columns
        assert "phone" not in columns
        assert customer.email_hash != "buyer@example.com"
        assert len(customer.email_hash) == 64  # sha256 hex digest length


@pytest.mark.db
class TestOrdersIngestLinksCustomer:
    """End-to-end via the real POST /stores/{id}/orders route, not just the
    service function directly."""

    def test_bulk_ingest_resolves_and_dedupes_customer_id(self, client, auth_header, test_store, test_db_session):
        response = client.post(
            f"/stores/{test_store.id}/orders",
            headers=auth_header,
            json=[
                {
                    "order_id": "order-1",
                    "time": "2026-01-01T00:00:00Z",
                    "gross_amount": 50.0,
                    "currency": "USD",
                    "customer_email": "repeat@example.com",
                },
                {
                    "order_id": "order-2",
                    "time": "2026-01-05T00:00:00Z",
                    "gross_amount": 75.0,
                    "currency": "USD",
                    "customer_email": "repeat@example.com",
                },
            ],
        )
        assert response.status_code == status.HTTP_201_CREATED

        orders_response = client.get(f"/stores/{test_store.id}/orders", headers=auth_header)
        customer_ids = {o["customer_id"] for o in orders_response.json()}
        assert len(customer_ids) == 1
        assert None not in customer_ids
        assert test_db_session.query(Customer).filter_by(store_id=test_store.id).count() == 1

    def test_order_with_no_customer_info_has_null_customer_id(self, client, auth_header, test_store):
        response = client.post(
            f"/stores/{test_store.id}/orders",
            headers=auth_header,
            json=[
                {
                    "order_id": "order-anon",
                    "time": "2026-01-01T00:00:00Z",
                    "gross_amount": 50.0,
                    "currency": "USD",
                }
            ],
        )
        assert response.status_code == status.HTTP_201_CREATED

        orders_response = client.get(f"/stores/{test_store.id}/orders", headers=auth_header)
        order = next(o for o in orders_response.json() if o["order_id"] == "order-anon")
        assert order["customer_id"] is None
