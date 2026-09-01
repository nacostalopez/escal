"""Tests verifying every connector normalizes its output to a consistent schema.

Meta and Google both feed the ad_spend table and must produce the same field
set. Shopify feeds the orders table and must satisfy OrderCreate. HTTP calls
are mocked — these are schema/shape checks, not live integration tests.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.connectors.google import GoogleAdsConnector
from app.connectors.meta import MetaConnector
from app.connectors.shopify import ShopifyConnector

AD_SPEND_REQUIRED_FIELDS = {
    "time", "platform", "campaign_id", "campaign_name",
    "adset_id", "spend", "impressions", "clicks",
}
ORDER_REQUIRED_FIELDS = {
    "order_id", "time", "gross_amount", "discounts", "shipping_fee",
    "payment_gateway_fee", "cogs_total", "currency",
    "attribution_utm_source", "attribution_utm_campaign",
}


def _mock_response(payload):
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status = MagicMock()
    return response


@pytest.mark.connector
class TestAdSpendSchemaConsistency:
    """Meta and Google must both feed the same ad_spend table with the same shape."""

    def test_meta_ad_spend_record_shape(self):
        connector = MetaConnector(store_id="store-1", ad_account_id="act_123")
        response = _mock_response({
            "data": [{
                "campaign_id": "1", "campaign_name": "Test Campaign", "adset_id": "10",
                "spend": "12.50", "impressions": "1000", "clicks": "20",
                "date_start": "2026-01-01",
            }],
            "paging": {},
        })
        with patch("app.connectors.meta.requests.get", return_value=response):
            records = connector.fetch_ad_spend(
                "fake-token",
                datetime(2026, 1, 1, tzinfo=timezone.utc),
                datetime(2026, 1, 31, tzinfo=timezone.utc),
            )
        assert len(records) == 1
        assert AD_SPEND_REQUIRED_FIELDS.issubset(records[0].keys())
        assert records[0]["platform"] == "meta"

    def test_google_ad_spend_record_shape(self):
        connector = GoogleAdsConnector(store_id="store-1", customer_id="123")
        response = _mock_response({
            "results": [{
                "campaign": {"id": "1", "name": "Test Campaign"},
                "ad_group": {"id": "10"},
                "metrics": {"cost_micros": 12500000, "impressions": 1000, "clicks": 20},
                "segments": {"date": "2026-01-01"},
            }],
        })
        with patch("app.connectors.google.requests.post", return_value=response):
            records = connector.fetch_ad_spend(
                "fake-token",
                datetime(2026, 1, 1, tzinfo=timezone.utc),
                datetime(2026, 1, 31, tzinfo=timezone.utc),
            )
        assert len(records) == 1
        assert AD_SPEND_REQUIRED_FIELDS.issubset(records[0].keys())
        assert records[0]["platform"] == "google"

    def test_meta_and_google_produce_identical_field_sets(self):
        """Whatever field one ad-spend connector adds, the other must too."""
        meta_connector = MetaConnector(store_id="store-1", ad_account_id="act_123")
        google_connector = GoogleAdsConnector(store_id="store-1", customer_id="123")

        meta_response = _mock_response({
            "data": [{
                "campaign_id": "1", "campaign_name": "C", "adset_id": "10",
                "spend": "1", "impressions": "1", "clicks": "1", "date_start": "2026-01-01",
            }],
            "paging": {},
        })
        google_response = _mock_response({
            "results": [{
                "campaign": {"id": "1", "name": "C"}, "ad_group": {"id": "10"},
                "metrics": {"cost_micros": 1000000, "impressions": 1, "clicks": 1},
                "segments": {"date": "2026-01-01"},
            }],
        })

        with patch("app.connectors.meta.requests.get", return_value=meta_response):
            meta_records = meta_connector.fetch_ad_spend(
                "t", datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 31, tzinfo=timezone.utc)
            )
        with patch("app.connectors.google.requests.post", return_value=google_response):
            google_records = google_connector.fetch_ad_spend(
                "t", datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 31, tzinfo=timezone.utc)
            )

        assert set(meta_records[0].keys()) == set(google_records[0].keys())


@pytest.mark.connector
class TestOrderSchemaConsistency:
    """Shopify's normalized order output must satisfy OrderCreate's required fields."""

    def test_shopify_order_webhook_shape(self):
        connector = ShopifyConnector(store_id="store-1")
        shopify_order = {
            "id": 123456,
            "total_price": "100.00",
            "total_discounts": "0.00",
            "shipping_lines": [{"price": "4.99"}],
            "transactions": [{"kind": "capture", "gateway_fee": "3.20"}],
            "line_items": [],
            "created_at": "2026-01-01T00:00:00Z",
            "currency": "USD",
            "note": "utm_source=meta&utm_campaign=demo",
        }
        result = connector.process_webhook("orders/create", shopify_order)
        assert ORDER_REQUIRED_FIELDS.issubset(result.keys())
        assert result["order_id"] == "123456"
        assert result["attribution_utm_source"] == "meta"
        assert result["attribution_utm_campaign"] == "demo"
