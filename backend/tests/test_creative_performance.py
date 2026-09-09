"""Tests for creative-level (ad-level) performance ingestion and the
aggregated /metrics/creatives ranking used by the frontend widget.
"""

import pytest
from fastapi import status


@pytest.mark.db
class TestIngestCreativePerformance:
    def test_ingest_and_list(self, client, auth_header, test_store):
        response = client.post(
            f"/stores/{test_store.id}/creative-performance",
            headers=auth_header,
            json=[
                {
                    "time": "2026-01-05T00:00:00Z",
                    "platform": "meta",
                    "campaign_id": "c1",
                    "campaign_name": "Campaign 1",
                    "adset_id": "as1",
                    "ad_id": "ad1",
                    "ad_name": "Creative A",
                    "spend": 25.5,
                    "impressions": 1000,
                    "clicks": 20,
                }
            ],
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["inserted"] == 1

        list_response = client.get(f"/stores/{test_store.id}/creative-performance", headers=auth_header)
        assert list_response.status_code == status.HTTP_200_OK
        assert len(list_response.json()) == 1
        assert list_response.json()[0]["ad_name"] == "Creative A"

    def test_empty_payload_is_a_no_op(self, client, auth_header, test_store):
        response = client.post(f"/stores/{test_store.id}/creative-performance", headers=auth_header, json=[])
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["inserted"] == 0

    def test_viewer_cannot_ingest(self, client, viewer_auth_header, test_store):
        response = client.post(
            f"/stores/{test_store.id}/creative-performance",
            headers=viewer_auth_header,
            json=[
                {
                    "time": "2026-01-05T00:00:00Z",
                    "platform": "meta",
                    "campaign_id": "c1",
                    "ad_id": "ad1",
                    "spend": 1.0,
                }
            ],
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.db
class TestCreativesMetricsRanking:
    def _seed(self, client, auth_header, store_id, rows):
        response = client.post(f"/stores/{store_id}/creative-performance", headers=auth_header, json=rows)
        assert response.status_code == status.HTTP_201_CREATED

    def test_ranked_by_spend_descending(self, client, auth_header, test_store):
        self._seed(
            client,
            auth_header,
            test_store.id,
            [
                {
                    "time": "2026-01-05T00:00:00Z",
                    "platform": "meta",
                    "campaign_id": "c1",
                    "campaign_name": "Camp",
                    "ad_id": "cheap-ad",
                    "ad_name": "Cheap",
                    "spend": 10.0,
                    "impressions": 1000,
                    "clicks": 10,
                },
                {
                    "time": "2026-01-05T00:00:00Z",
                    "platform": "meta",
                    "campaign_id": "c1",
                    "campaign_name": "Camp",
                    "ad_id": "expensive-ad",
                    "ad_name": "Expensive",
                    "spend": 500.0,
                    "impressions": 5000,
                    "clicks": 100,
                },
            ],
        )

        response = client.get(
            f"/stores/{test_store.id}/metrics/creatives?start=2026-01-01T00:00:00Z&end=2026-01-31T00:00:00Z",
            headers=auth_header,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        assert data[0]["ad_id"] == "expensive-ad"
        assert data[1]["ad_id"] == "cheap-ad"

    def test_sums_across_multiple_days_for_the_same_ad(self, client, auth_header, test_store):
        self._seed(
            client,
            auth_header,
            test_store.id,
            [
                {
                    "time": "2026-01-05T00:00:00Z",
                    "platform": "meta",
                    "campaign_id": "c1",
                    "ad_id": "ad1",
                    "ad_name": "Creative A",
                    "spend": 10.0,
                    "impressions": 1000,
                    "clicks": 10,
                },
                {
                    "time": "2026-01-06T00:00:00Z",
                    "platform": "meta",
                    "campaign_id": "c1",
                    "ad_id": "ad1",
                    "ad_name": "Creative A",
                    "spend": 15.0,
                    "impressions": 500,
                    "clicks": 5,
                },
            ],
        )

        response = client.get(
            f"/stores/{test_store.id}/metrics/creatives?start=2026-01-01T00:00:00Z&end=2026-01-31T00:00:00Z",
            headers=auth_header,
        )
        data = response.json()
        assert len(data) == 1
        assert data[0]["spend"] == 25.0
        assert data[0]["impressions"] == 1500
        assert data[0]["clicks"] == 15

    def test_ctr_cpc_cpm_are_computed(self, client, auth_header, test_store):
        self._seed(
            client,
            auth_header,
            test_store.id,
            [
                {
                    "time": "2026-01-05T00:00:00Z",
                    "platform": "meta",
                    "campaign_id": "c1",
                    "ad_id": "ad1",
                    "ad_name": "Creative A",
                    "spend": 100.0,
                    "impressions": 10000,
                    "clicks": 200,
                }
            ],
        )

        response = client.get(
            f"/stores/{test_store.id}/metrics/creatives?start=2026-01-01T00:00:00Z&end=2026-01-31T00:00:00Z",
            headers=auth_header,
        )
        row = response.json()[0]
        assert row["ctr"] == 2.0  # 200/10000 * 100
        assert row["cpc"] == 0.5  # 100/200
        assert row["cpm"] == 10.0  # 100/10000 * 1000

    def test_zero_impressions_does_not_error(self, client, auth_header, test_store):
        self._seed(
            client,
            auth_header,
            test_store.id,
            [
                {
                    "time": "2026-01-05T00:00:00Z",
                    "platform": "meta",
                    "campaign_id": "c1",
                    "ad_id": "ad1",
                    "spend": 5.0,
                    "impressions": 0,
                    "clicks": 0,
                }
            ],
        )

        response = client.get(
            f"/stores/{test_store.id}/metrics/creatives?start=2026-01-01T00:00:00Z&end=2026-01-31T00:00:00Z",
            headers=auth_header,
        )
        row = response.json()[0]
        assert row["ctr"] is None
        assert row["cpc"] is None
        assert row["cpm"] is None

    def test_out_of_range_rows_excluded(self, client, auth_header, test_store):
        self._seed(
            client,
            auth_header,
            test_store.id,
            [
                {
                    "time": "2025-06-01T00:00:00Z",
                    "platform": "meta",
                    "campaign_id": "c1",
                    "ad_id": "old-ad",
                    "spend": 50.0,
                    "impressions": 100,
                    "clicks": 5,
                }
            ],
        )

        response = client.get(
            f"/stores/{test_store.id}/metrics/creatives?start=2026-01-01T00:00:00Z&end=2026-01-31T00:00:00Z",
            headers=auth_header,
        )
        assert response.json() == []
