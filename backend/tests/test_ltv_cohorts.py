"""Tests for GET /metrics/ltv-cohorts (LTV by acquisition cohort + blended
CAC payback), built on top of the customer identity foundation.
"""

import pytest
from fastapi import status


@pytest.mark.db
class TestLtvCohorts:
    def _seed_orders(self, client, auth_header, store_id, rows):
        response = client.post(f"/stores/{store_id}/orders", headers=auth_header, json=rows)
        assert response.status_code == status.HTTP_201_CREATED

    def _seed_ad_spend(self, client, auth_header, store_id, rows):
        response = client.post(f"/stores/{store_id}/ad-spend", headers=auth_header, json=rows)
        assert response.status_code == status.HTTP_201_CREATED

    def test_single_cohort_sums_net_profit_with_no_spend_data(self, client, auth_header, test_store):
        self._seed_orders(
            client,
            auth_header,
            test_store.id,
            [
                {
                    "order_id": "order-1",
                    "time": "2026-01-05T00:00:00Z",
                    "gross_amount": 50.0,
                    "currency": "USD",
                    "customer_email": "solo@example.com",
                },
                {
                    "order_id": "order-2",
                    "time": "2026-01-10T00:00:00Z",
                    "gross_amount": 30.0,
                    "currency": "USD",
                    "customer_email": "solo@example.com",
                },
            ],
        )

        response = client.get(
            f"/stores/{test_store.id}/metrics/ltv-cohorts?start=2026-01-01T00:00:00Z&end=2026-01-31T00:00:00Z&months=3",
            headers=auth_header,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        cohort = data[0]
        assert cohort["cohort_month"] == "2026-01-01"
        assert cohort["new_customers"] == 1
        assert cohort["cac"] is None
        assert cohort["payback_month"] is None
        assert cohort["ltv_by_month"] == [80.0, 80.0, 80.0]

    def test_gap_month_is_forward_filled(self, client, auth_header, test_store):
        self._seed_orders(
            client,
            auth_header,
            test_store.id,
            [
                {
                    "order_id": "order-1",
                    "time": "2026-02-05T00:00:00Z",
                    "gross_amount": 40.0,
                    "currency": "USD",
                    "customer_email": "repeat@example.com",
                },
                {
                    "order_id": "order-2",
                    "time": "2026-04-05T00:00:00Z",
                    "gross_amount": 20.0,
                    "currency": "USD",
                    "customer_email": "repeat@example.com",
                },
            ],
        )

        response = client.get(
            f"/stores/{test_store.id}/metrics/ltv-cohorts?start=2026-02-01T00:00:00Z&end=2026-02-28T00:00:00Z&months=3",
            headers=auth_header,
        )
        data = response.json()
        assert len(data) == 1
        # Month 0 = Feb (order 1), month 1 = Mar (no order — forward-filled
        # from month 0), month 2 = Apr (order 2 added on top).
        assert data[0]["ltv_by_month"] == [40.0, 40.0, 60.0]

    def test_cac_and_payback_month_computed_from_ad_spend(self, client, auth_header, test_store):
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
                    "customer_email": "paid@example.com",
                },
            ],
        )
        self._seed_ad_spend(
            client,
            auth_header,
            test_store.id,
            [
                {
                    "time": "2026-03-01T00:00:00Z",
                    "platform": "meta",
                    "campaign_id": "c1",
                    "spend": 40.0,
                },
            ],
        )

        response = client.get(
            f"/stores/{test_store.id}/metrics/ltv-cohorts?start=2026-03-01T00:00:00Z&end=2026-03-31T00:00:00Z&months=2",
            headers=auth_header,
        )
        data = response.json()
        assert len(data) == 1
        assert data[0]["cac"] == 40.0
        assert data[0]["ltv_by_month"] == [100.0, 100.0]
        assert data[0]["payback_month"] == 0

    def test_cohort_outside_range_excluded_even_with_orders_inside_it(self, client, auth_header, test_store):
        self._seed_orders(
            client,
            auth_header,
            test_store.id,
            [
                {
                    "order_id": "order-1",
                    "time": "2025-12-15T00:00:00Z",
                    "gross_amount": 60.0,
                    "currency": "USD",
                    "customer_email": "old@example.com",
                },
            ],
        )

        response = client.get(
            f"/stores/{test_store.id}/metrics/ltv-cohorts?start=2026-01-01T00:00:00Z&end=2026-01-31T00:00:00Z",
            headers=auth_header,
        )
        assert response.json() == []

    def test_two_customers_same_month_average_correctly(self, client, auth_header, test_store):
        self._seed_orders(
            client,
            auth_header,
            test_store.id,
            [
                {
                    "order_id": "order-1",
                    "time": "2026-05-05T00:00:00Z",
                    "gross_amount": 100.0,
                    "currency": "USD",
                    "customer_email": "cust-a@example.com",
                },
                {
                    "order_id": "order-2",
                    "time": "2026-05-06T00:00:00Z",
                    "gross_amount": 50.0,
                    "currency": "USD",
                    "customer_email": "cust-b@example.com",
                },
            ],
        )

        response = client.get(
            f"/stores/{test_store.id}/metrics/ltv-cohorts?start=2026-05-01T00:00:00Z&end=2026-05-31T00:00:00Z&months=1",
            headers=auth_header,
        )
        data = response.json()
        assert len(data) == 1
        assert data[0]["new_customers"] == 2
        assert data[0]["ltv_by_month"] == [75.0]
