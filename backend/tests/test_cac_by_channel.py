"""Tests for GET /metrics/cac-by-channel — CAC split by acquisition
channel, unlike ltv-cohorts' blended CAC (see test_ltv_cohorts.py).
"""

import pytest
from fastapi import status


@pytest.mark.db
class TestCacByChannel:
    def _seed_orders(self, client, auth_header, store_id, rows):
        response = client.post(f"/stores/{store_id}/orders", headers=auth_header, json=rows)
        assert response.status_code == status.HTTP_201_CREATED

    def _seed_ad_spend(self, client, auth_header, store_id, rows):
        response = client.post(f"/stores/{store_id}/ad-spend", headers=auth_header, json=rows)
        assert response.status_code == status.HTTP_201_CREATED

    def test_splits_cac_by_each_customers_first_order_channel(self, client, auth_header, test_store):
        self._seed_orders(
            client,
            auth_header,
            test_store.id,
            [
                {
                    "order_id": "order-1",
                    "time": "2026-03-05T00:00:00Z",
                    "gross_amount": 100.0,
                    "currency": "USD",
                    "customer_email": "meta-buyer@example.com",
                    "attribution_utm_source": "meta",
                },
                {
                    "order_id": "order-2",
                    "time": "2026-03-06T00:00:00Z",
                    "gross_amount": 50.0,
                    "currency": "USD",
                    "customer_email": "google-buyer@example.com",
                    "attribution_utm_source": "google",
                },
            ],
        )
        self._seed_ad_spend(
            client,
            auth_header,
            test_store.id,
            [
                {"time": "2026-03-01T00:00:00Z", "platform": "meta", "campaign_id": "c1", "spend": 40.0},
                {"time": "2026-03-01T00:00:00Z", "platform": "google", "campaign_id": "c2", "spend": 20.0},
            ],
        )

        response = client.get(
            f"/stores/{test_store.id}/metrics/cac-by-channel?start=2026-03-01T00:00:00Z&end=2026-03-31T00:00:00Z",
            headers=auth_header,
        )
        assert response.status_code == status.HTTP_200_OK
        data = {row["channel"]: row for row in response.json()}
        assert data["meta"]["new_customers"] == 1
        assert data["meta"]["spend"] == 40.0
        assert data["meta"]["cac"] == 40.0
        assert data["google"]["new_customers"] == 1
        assert data["google"]["spend"] == 20.0
        assert data["google"]["cac"] == 20.0

    def test_unrecognized_utm_source_falls_back_to_other_with_no_cac(self, client, auth_header, test_store):
        self._seed_orders(
            client,
            auth_header,
            test_store.id,
            [
                {
                    "order_id": "order-1",
                    "time": "2026-04-05T00:00:00Z",
                    "gross_amount": 30.0,
                    "currency": "USD",
                    "customer_email": "organic@example.com",
                    "attribution_utm_source": "newsletter",
                },
            ],
        )

        response = client.get(
            f"/stores/{test_store.id}/metrics/cac-by-channel?start=2026-04-01T00:00:00Z&end=2026-04-30T00:00:00Z",
            headers=auth_header,
        )
        data = response.json()
        assert len(data) == 1
        assert data[0]["channel"] == "other"
        assert data[0]["new_customers"] == 1
        assert data[0]["spend"] is None
        assert data[0]["cac"] is None

    def test_utm_source_alias_normalizes_to_meta(self, client, auth_header, test_store):
        self._seed_orders(
            client,
            auth_header,
            test_store.id,
            [
                {
                    "order_id": "order-1",
                    "time": "2026-05-05T00:00:00Z",
                    "gross_amount": 60.0,
                    "currency": "USD",
                    "customer_email": "fb-buyer@example.com",
                    "attribution_utm_source": "Facebook",
                },
            ],
        )

        response = client.get(
            f"/stores/{test_store.id}/metrics/cac-by-channel?start=2026-05-01T00:00:00Z&end=2026-05-31T00:00:00Z",
            headers=auth_header,
        )
        data = response.json()
        assert len(data) == 1
        assert data[0]["channel"] == "meta"

    def test_second_order_channel_does_not_change_acquisition_channel(self, client, auth_header, test_store):
        """A customer's channel is fixed at their first order, even if a
        later order carries a different attribution_utm_source."""
        self._seed_orders(
            client,
            auth_header,
            test_store.id,
            [
                {
                    "order_id": "order-1",
                    "time": "2026-06-05T00:00:00Z",
                    "gross_amount": 60.0,
                    "currency": "USD",
                    "customer_email": "loyal@example.com",
                    "attribution_utm_source": "meta",
                },
                {
                    "order_id": "order-2",
                    "time": "2026-06-20T00:00:00Z",
                    "gross_amount": 20.0,
                    "currency": "USD",
                    "customer_email": "loyal@example.com",
                    "attribution_utm_source": "google",
                },
            ],
        )

        response = client.get(
            f"/stores/{test_store.id}/metrics/cac-by-channel?start=2026-06-01T00:00:00Z&end=2026-06-30T00:00:00Z",
            headers=auth_header,
        )
        data = response.json()
        assert len(data) == 1
        assert data[0]["channel"] == "meta"
        assert data[0]["new_customers"] == 1
