"""Google Ads connector for ad spend tracking."""

from datetime import datetime, timedelta
from typing import List, Optional

import requests
from pydantic_settings import BaseSettings

from app.connectors import BaseConnector, OAuthToken


class GoogleSettings(BaseSettings):
    """Google Ads-specific configuration."""

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:3000/auth/google/callback"
    google_scopes: str = "https://www.googleapis.com/auth/adwords"
    google_developer_token: str = ""

    class Config:
        env_file = ".env"


class GoogleAdsConnector(BaseConnector):
    """Google Ads connector for OAuth and ad spend tracking."""

    API_VERSION = "v15"
    API_BASE = f"https://googleads.googleapis.com/{API_VERSION}"
    OAUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    # Bump API_VERSION when Google sunsets it (~1yr cycle) and log what changed here.
    BREAKING_CHANGES = [
        "v15: initial implementation",
    ]

    def __init__(self, store_id: str, customer_id: Optional[str] = None):
        super().__init__(store_id, "google")
        self.settings = GoogleSettings()
        self.customer_id = customer_id  # e.g., "1234567890"

    def get_oauth_url(self, state: str) -> str:
        """Get Google OAuth authorization URL."""
        from urllib.parse import urlencode

        params = {
            "client_id": self.settings.google_client_id,
            "redirect_uri": self.settings.google_redirect_uri,
            "scope": self.settings.google_scopes,
            "response_type": "code",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }

        return f"{self.OAUTH_URL}?{urlencode(params)}"

    def exchange_auth_code(self, code: str, redirect_uri: str) -> OAuthToken:
        """Exchange authorization code for access token."""
        payload = {
            "client_id": self.settings.google_client_id,
            "client_secret": self.settings.google_client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }

        response = requests.post(self.TOKEN_URL, data=payload)
        response.raise_for_status()

        data = response.json()

        # Google returns refresh token on first auth
        expires_at = None
        if "expires_in" in data:
            expires_at = datetime.utcnow() + timedelta(seconds=data["expires_in"])

        return OAuthToken(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=expires_at,
        )

    def validate_webhook_signature(self, body: str, signature: str) -> bool:
        """Google Ads doesn't use webhooks; validation not needed."""
        return True

    def process_webhook(self, event_type: str, data: dict) -> dict:
        """Google Ads doesn't use webhooks."""
        raise NotImplementedError("Google Ads does not use webhooks")

    def refresh_access_token(self, refresh_token: str) -> OAuthToken:
        """Refresh access token using refresh token."""
        payload = {
            "client_id": self.settings.google_client_id,
            "client_secret": self.settings.google_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        response = requests.post(self.TOKEN_URL, data=payload)
        response.raise_for_status()

        data = response.json()

        expires_at = None
        if "expires_in" in data:
            expires_at = datetime.utcnow() + timedelta(seconds=data["expires_in"])

        return OAuthToken(
            access_token=data["access_token"],
            refresh_token=refresh_token,  # Refresh token stays the same
            expires_at=expires_at,
        )

    def fetch_ad_spend(
        self,
        access_token: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[dict]:
        """Fetch ad spend data from Google Ads API using GAQL.

        Args:
            access_token: Google API access token
            start_date: Start date for data fetch
            end_date: End date for data fetch

        Returns:
            List of ad spend records
        """
        if not self.customer_id:
            raise ValueError("customer_id required for ad spend fetch")

        url = f"{self.API_BASE}/customers/{self.customer_id}/googleAds:search"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "developer-token": self.settings.google_developer_token,
        }

        # GAQL query to fetch campaign performance
        query = f"""
            SELECT
                campaign.id,
                campaign.name,
                ad_group.id,
                ad_group.name,
                metrics.cost_micros,
                metrics.impressions,
                metrics.clicks,
                segments.date
            FROM ad_group_ad
            WHERE segments.date >= '{start_date.date().isoformat()}'
            AND segments.date <= '{end_date.date().isoformat()}'
            AND campaign.status = ENABLED
        """

        payload = {"query": query}

        spend_records = []

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        data = response.json()

        for result in data.get("results", []):
            record = {
                "time": datetime.fromisoformat(result.get("segments", {}).get("date", datetime.utcnow().isoformat())),
                "platform": "google",
                "campaign_id": str(result.get("campaign", {}).get("id", "")),
                "campaign_name": result.get("campaign", {}).get("name", ""),
                "adset_id": str(result.get("ad_group", {}).get("id", "")),
                "spend": result.get("metrics", {}).get("cost_micros", 0) / 1_000_000,  # Convert from micros
                "impressions": result.get("metrics", {}).get("impressions", 0),
                "clicks": result.get("metrics", {}).get("clicks", 0),
            }
            spend_records.append(record)

        return spend_records

    def fetch_creative_performance(
        self,
        access_token: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[dict]:
        """Ad-level (creative) breakdown for the creative_performance table.

        fetch_ad_spend already queries the ad_group_ad resource (its FROM
        clause), but only selects campaign/ad_group fields — this adds
        ad_group_ad.ad.id/name, the individual ad's own identity. thumbnail
        isn't fetched — Google Ads doesn't expose creative assets over this
        API without a separate asset-report call per ad.
        """
        if not self.customer_id:
            raise ValueError("customer_id required for creative performance fetch")

        url = f"{self.API_BASE}/customers/{self.customer_id}/googleAds:search"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "developer-token": self.settings.google_developer_token,
        }

        query = f"""
            SELECT
                campaign.id,
                campaign.name,
                ad_group.id,
                ad_group_ad.ad.id,
                ad_group_ad.ad.name,
                metrics.cost_micros,
                metrics.impressions,
                metrics.clicks,
                segments.date
            FROM ad_group_ad
            WHERE segments.date >= '{start_date.date().isoformat()}'
            AND segments.date <= '{end_date.date().isoformat()}'
            AND campaign.status = ENABLED
        """

        payload = {"query": query}

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        data = response.json()

        records = []
        for result in data.get("results", []):
            ad = result.get("ad_group_ad", {}).get("ad", {})
            ad_id = str(ad.get("id", ""))
            records.append(
                {
                    "time": datetime.fromisoformat(
                        result.get("segments", {}).get("date", datetime.utcnow().isoformat())
                    ),
                    "platform": "google",
                    "campaign_id": str(result.get("campaign", {}).get("id", "")),
                    "campaign_name": result.get("campaign", {}).get("name", ""),
                    "adset_id": str(result.get("ad_group", {}).get("id", "")),
                    "ad_id": ad_id,
                    # Responsive search ads often have no name — fall back to
                    # the id so the frontend never shows a blank creative label.
                    "ad_name": ad.get("name") or f"Ad {ad_id}",
                    "thumbnail_url": None,
                    "spend": result.get("metrics", {}).get("cost_micros", 0) / 1_000_000,
                    "impressions": result.get("metrics", {}).get("impressions", 0),
                    "clicks": result.get("metrics", {}).get("clicks", 0),
                }
            )

        return records

    def fetch_historical_data(
        self,
        access_token: str,
        start_date: datetime,
        end_date: datetime,
    ) -> dict:
        """Fetch historical ad spend data."""
        return {"spend_records": self.fetch_ad_spend(access_token, start_date, end_date)}
