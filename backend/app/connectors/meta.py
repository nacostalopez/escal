"""Meta (Facebook) Ads connector for ad spend tracking."""
from typing import Optional, List
from datetime import datetime, timedelta
import hashlib
import hmac
import json

import requests
from pydantic_settings import BaseSettings

from app.connectors import BaseConnector, OAuthToken


class MetaSettings(BaseSettings):
    """Meta-specific configuration."""
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_redirect_uri: str = "http://localhost:3000/auth/meta/callback"
    meta_scopes: str = "ads_management,ads_read"

    class Config:
        env_file = ".env"


class MetaConnector(BaseConnector):
    """Meta (Facebook) Ads connector for OAuth and ad spend tracking."""

    API_VERSION = "v19.0"
    API_BASE = f"https://graph.facebook.com/{API_VERSION}"

    def __init__(self, store_id: str, ad_account_id: Optional[str] = None):
        super().__init__(store_id, "meta")
        self.settings = MetaSettings()
        self.ad_account_id = ad_account_id  # e.g., "act_123456789"

    def get_oauth_url(self, state: str) -> str:
        """Get Meta OAuth authorization URL."""
        params = {
            "client_id": self.settings.meta_app_id,
            "redirect_uri": self.settings.meta_redirect_uri,
            "scope": self.settings.meta_scopes,
            "response_type": "code",
            "state": state,
        }

        from urllib.parse import urlencode
        return f"https://www.facebook.com/{self.API_VERSION}/dialog/oauth?{urlencode(params)}"

    def exchange_auth_code(self, code: str, redirect_uri: str) -> OAuthToken:
        """Exchange authorization code for access token."""
        url = f"{self.API_BASE}/oauth/access_token"

        params = {
            "client_id": self.settings.meta_app_id,
            "client_secret": self.settings.meta_app_secret,
            "redirect_uri": redirect_uri,
            "code": code,
        }

        response = requests.get(url, params=params)
        response.raise_for_status()

        data = response.json()

        return OAuthToken(
            access_token=data["access_token"],
            refresh_token=None,  # Meta doesn't use refresh tokens
            expires_at=None,  # Access tokens don't expire for business accounts
        )

    def validate_webhook_signature(self, body: str, signature: str) -> bool:
        """Validate webhook signature.
        
        Meta sends X-Hub-Signature header with SHA1 HMAC.
        """
        expected = hmac.new(
            self.settings.meta_app_secret.encode(),
            body.encode(),
            hashlib.sha1,
        ).hexdigest()

        return hmac.compare_digest(f"sha1={expected}", signature)

    def process_webhook(self, event_type: str, data: dict) -> dict:
        """Process webhook event.
        
        For ads, we typically receive:
        - campaign performance updates
        - billing events
        - ad account changes
        """
        if event_type == "ad_account_update":
            return {"status": "acknowledged"}
        else:
            raise ValueError(f"Unsupported event type: {event_type}")

    def fetch_ad_spend(
        self,
        access_token: str,
        start_date: datetime,
        end_date: datetime,
        breakdown_by: str = "campaign",
    ) -> List[dict]:
        """Fetch ad spend data from Meta Ads API.
        
        Args:
            access_token: Meta API access token
            start_date: Start date for data fetch
            end_date: End date for data fetch
            breakdown_by: "campaign", "adset", or "ad"
            
        Returns:
            List of ad spend records
        """
        if not self.ad_account_id:
            raise ValueError("ad_account_id required for ad spend fetch")

        url = f"{self.API_BASE}/{self.ad_account_id}/insights"

        params = {
            "access_token": access_token,
            "time_range": json.dumps({
                "since": start_date.date().isoformat(),
                "until": end_date.date().isoformat(),
            }),
            "fields": ",".join([
                "campaign_id",
                "campaign_name",
                "adset_id",
                "adset_name",
                "ad_id",
                "ad_name",
                "spend",
                "impressions",
                "clicks",
                "date_start",
                "date_stop",
            ]),
            "breakdowns": breakdown_by,
            "limit": 100,
        }

        spend_records = []

        while url:
            response = requests.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            for insight in data.get("data", []):
                record = {
                    "time": datetime.fromisoformat(
                        insight.get("date_start", datetime.utcnow().isoformat())
                    ),
                    "platform": "meta",
                    "campaign_id": str(insight.get("campaign_id", "")),
                    "campaign_name": insight.get("campaign_name", ""),
                    "adset_id": str(insight.get("adset_id", "")),
                    "spend": float(insight.get("spend", 0)),
                    "impressions": int(insight.get("impressions", 0)),
                    "clicks": int(insight.get("clicks", 0)),
                }
                spend_records.append(record)

            # Handle pagination
            paging = data.get("paging", {})
            if "cursors" in paging and "after" in paging["cursors"]:
                params["after"] = paging["cursors"]["after"]
            else:
                break

        return spend_records

    def fetch_historical_data(
        self,
        access_token: str,
        start_date: datetime,
        end_date: datetime,
    ) -> dict:
        """Fetch historical ad spend data."""
        return {
            "spend_records": self.fetch_ad_spend(access_token, start_date, end_date)
        }
