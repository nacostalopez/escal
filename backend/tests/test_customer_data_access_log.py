"""Tests for the customer-data access log — GET /orders logs an entry
(the only route that returns anything customer-linked, see
app/models/audit.py::CustomerDataAccessLog), GET /orders/audit-log reads
it back.
"""
import pytest
from fastapi import status

from app.models import CustomerDataAccessLog


def _login(client, email, password):
    response = client.post("/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.db
class TestCustomerDataAccessLogging:
    def test_listing_orders_records_an_access_log_entry(
        self, client, auth_header, test_store, test_db_session, test_user
    ):
        client.get(f"/stores/{test_store.id}/orders", headers=auth_header)

        entries = test_db_session.query(CustomerDataAccessLog).filter_by(store_id=test_store.id).all()
        assert len(entries) == 1
        assert entries[0].user_id == test_user.id
        assert entries[0].endpoint == "GET /orders"

    def test_each_listing_adds_its_own_entry(self, client, auth_header, test_store, test_db_session):
        client.get(f"/stores/{test_store.id}/orders", headers=auth_header)
        client.get(f"/stores/{test_store.id}/orders", headers=auth_header)

        count = test_db_session.query(CustomerDataAccessLog).filter_by(store_id=test_store.id).count()
        assert count == 2


@pytest.mark.db
class TestAuditLogEndpoint:
    def test_owner_sees_who_accessed_orders(self, client, auth_header, test_store, test_user):
        client.get(f"/stores/{test_store.id}/orders", headers=auth_header)

        response = client.get(f"/stores/{test_store.id}/orders/audit-log", headers=auth_header)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["user_email"] == "testuser@example.com"
        assert data[0]["endpoint"] == "GET /orders"

    def test_viewer_cannot_read_audit_log(self, client, test_store, viewer_user):
        viewer_header = _login(client, "viewer@example.com", "viewerpassword123")
        response = client.get(f"/stores/{test_store.id}/orders/audit-log", headers=viewer_header)
        assert response.status_code == status.HTTP_403_FORBIDDEN
