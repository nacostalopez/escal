"""Tests for ownership scoping - ensuring users can only access their account's data."""
import pytest
from fastapi import status
from uuid import uuid4


class TestOwnershipScoping:
    """Test that ownership scoping prevents unauthorized access."""

    def test_cannot_access_other_account_store(self, client, test_store, other_account, auth_header, test_db_session):
        """Test that a user cannot access a store from another account."""
        # Create a store in a different account
        from app.models import Store
        
        other_store = Store(
            id=uuid4(),
            account_id=other_account.id,
            name="Other Account Store",
            platform="shopify",
        )
        test_db_session.add(other_store)
        test_db_session.commit()
        
        # Try to access the other store
        response = client.get(
            f"/stores/{other_store.id}/orders",
            headers=auth_header,
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Store not found" in response.json()["detail"]

    def test_can_access_own_account_store(self, client, test_store, auth_header):
        """Test that a user can access stores in their own account."""
        response = client.get(
            f"/stores/{test_store.id}/orders",
            headers=auth_header,
        )
        
        # Should succeed (may have no orders, but should not 404)
        assert response.status_code in (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT)

    def test_ingest_orders_ownership_check(self, client, test_store, other_account, auth_header, test_db_session):
        """Test that order ingestion checks ownership."""
        from app.models import Store
        
        # Create a store in another account
        other_store = Store(
            id=uuid4(),
            account_id=other_account.id,
            name="Other Account Store",
            platform="shopify",
        )
        test_db_session.add(other_store)
        test_db_session.commit()
        
        # Try to ingest orders to the other store
        response = client.post(
            f"/stores/{other_store.id}/orders",
            headers=auth_header,
            json=[
                {
                    "order_id": "test_order_123",
                    "time": "2026-01-01T00:00:00Z",
                    "gross_amount": 100.0,
                    "currency": "USD",
                }
            ],
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Store not found" in response.json()["detail"]

    def test_list_orders_ownership_check(self, client, other_account, auth_header, test_db_session):
        """Test that listing orders checks ownership."""
        from app.models import Store
        
        other_store = Store(
            id=uuid4(),
            account_id=other_account.id,
            name="Other Account Store",
            platform="shopify",
        )
        test_db_session.add(other_store)
        test_db_session.commit()
        
        response = client.get(
            f"/stores/{other_store.id}/orders",
            headers=auth_header,
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Store not found" in response.json()["detail"]

    def test_ad_spend_ownership_check(self, client, other_account, auth_header, test_db_session):
        """Test that ad spend endpoints check ownership."""
        from app.models import Store
        
        other_store = Store(
            id=uuid4(),
            account_id=other_account.id,
            name="Other Account Store",
            platform="shopify",
        )
        test_db_session.add(other_store)
        test_db_session.commit()
        
        response = client.get(
            f"/stores/{other_store.id}/ad-spend",
            headers=auth_header,
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Store not found" in response.json()["detail"]

    def test_metrics_ownership_check(self, client, other_account, auth_header, test_db_session):
        """Test that metrics endpoints check ownership."""
        from app.models import Store
        
        other_store = Store(
            id=uuid4(),
            account_id=other_account.id,
            name="Other Account Store",
            platform="shopify",
        )
        test_db_session.add(other_store)
        test_db_session.commit()
        
        response = client.get(
            f"/stores/{other_store.id}/metrics/summary",
            headers=auth_header,
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Store not found" in response.json()["detail"]

    def test_no_data_leak_via_error_messages(self, client, other_account, auth_header, test_db_session):
        """Test that error messages don't leak information about other accounts."""
        from app.models import Store
        
        other_store = Store(
            id=uuid4(),
            account_id=other_account.id,
            name="Secret Store Name",
            platform="shopify",
        )
        test_db_session.add(other_store)
        test_db_session.commit()
        
        response = client.get(
            f"/stores/{other_store.id}/orders",
            headers=auth_header,
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        # Error message should not reveal the store exists
        detail = response.json()["detail"]
        assert "Secret Store Name" not in detail
        assert detail == "Store not found"
