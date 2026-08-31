"""Base classes and interfaces for connector implementations."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class OAuthToken:
    """OAuth token information."""
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    token_type: str = "Bearer"


class BaseConnector(ABC):
    """Base class for all connectors (Shopify, Meta, Google, etc.)."""

    def __init__(self, store_id, provider):
        self.store_id = store_id
        self.provider = provider

    @abstractmethod
    def get_oauth_url(self, state: str) -> str:
        """Get OAuth authorization URL."""
        pass

    @abstractmethod
    def exchange_auth_code(self, code: str, redirect_uri: str) -> OAuthToken:
        """Exchange authorization code for access token."""
        pass

    @abstractmethod
    def validate_webhook_signature(self, body: str, signature: str) -> bool:
        """Validate webhook signature to ensure it came from the provider."""
        pass

    @abstractmethod
    def process_webhook(self, event_type: str, data: dict) -> dict:
        """Process webhook event and return standardized data."""
        pass

    @abstractmethod
    def fetch_historical_data(self, start_date: datetime, end_date: datetime) -> dict:
        """Fetch historical data from the connector (e.g., orders, ad spend)."""
        pass
