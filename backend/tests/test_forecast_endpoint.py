"""Tests for GET /metrics/forecast — the API-level wiring around
app/services/forecasting.py::linear_forecast (see test_forecasting.py for
the pure-function coverage)."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import status


@pytest.mark.db
class TestForecastEndpoint:
    def _seed_orders(self, client, auth_header, store_id, rows):
        response = client.post(f"/stores/{store_id}/orders", headers=auth_header, json=rows)
        assert response.status_code == status.HTTP_201_CREATED

    def _seed_ad_spend(self, client, auth_header, store_id, rows):
        response = client.post(f"/stores/{store_id}/ad-spend", headers=auth_header, json=rows)
        assert response.status_code == status.HTTP_201_CREATED

    def test_insufficient_history_returns_empty_forecast(self, client, auth_header, test_store):
        # Only 2 days of orders — well under MIN_FORECAST_HISTORY_DAYS.
        now = datetime.now(timezone.utc)
        self._seed_orders(
            client,
            auth_header,
            test_store.id,
            [
                {
                    "order_id": "order-1",
                    "time": (now - timedelta(days=1)).isoformat(),
                    "gross_amount": 100.0,
                    "currency": "USD",
                },
            ],
        )

        response = client.get(f"/stores/{test_store.id}/metrics/forecast", headers=auth_header)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["days"] == []
        assert data["true_roas"] is None

    def test_upward_revenue_trend_forecasts_higher_than_last_history_day(
        self, client, auth_header, test_store
    ):
        now = datetime.now(timezone.utc)
        # 10 days of orders, revenue growing $10/day, plus flat ad spend so
        # true_roas has something to divide by.
        orders = []
        spend = []
        for i in range(10, 0, -1):
            day = now - timedelta(days=i)
            orders.append(
                {
                    "order_id": f"order-{i}",
                    "time": day.isoformat(),
                    "gross_amount": (10 - i) * 10.0 + 50.0,
                    "currency": "USD",
                }
            )
            spend.append({"time": day.isoformat(), "platform": "meta", "campaign_id": "c1", "spend": 20.0})
        self._seed_orders(client, auth_header, test_store.id, orders)
        self._seed_ad_spend(client, auth_header, test_store.id, spend)

        response = client.get(
            f"/stores/{test_store.id}/metrics/forecast?history_days=14&forecast_days=5",
            headers=auth_header,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["days"]) == 5
        # Forecast should keep climbing, and start above the last real day's revenue (~$140).
        assert data["days"][0]["revenue"] > 100.0
        assert data["days"][-1]["revenue"] > data["days"][0]["revenue"]
        assert data["total_ad_spend"] > 0

    def test_forecast_days_query_param_controls_length(self, client, auth_header, test_store):
        now = datetime.now(timezone.utc)
        orders = [
            {
                "order_id": f"order-{i}",
                "time": (now - timedelta(days=i)).isoformat(),
                "gross_amount": 50.0,
                "currency": "USD",
            }
            for i in range(1, 9)
        ]
        self._seed_orders(client, auth_header, test_store.id, orders)

        response = client.get(
            f"/stores/{test_store.id}/metrics/forecast?forecast_days=10", headers=auth_header
        )
        assert len(response.json()["days"]) == 10
