"""Connector routes for OAuth handshakes and webhooks."""
import hmac
import json
from uuid import uuid4, UUID
from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Header, Body, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import insert

from app.database import get_db
from app.dependencies import get_current_user, get_owned_store
from app.models import User, Store, StoreCredential
from app.security import encrypt_secret, decrypt_secret
from app.connectors.shopify import ShopifyConnector
from app.connectors.meta import MetaConnector
from app.connectors.google import GoogleAdsConnector

router = APIRouter(prefix="/connectors", tags=["connectors"])


@router.post("/shopify/auth-url")
def get_shopify_auth_url(
    store_id: UUID,
    shop_domain: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get Shopify OAuth authorization URL.
    
    Args:
        store_id: ID of store to connect
        shop_domain: Shopify shop domain (e.g., "mystore.myshopify.com")
        
    Returns:
        Authorization URL to redirect user to
    """
    store = db.get(Store, store_id)
    if not store or store.account_id != current_user.account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    
    # Generate state token for CSRF protection
    state_token = str(uuid4())
    
    # Store state in session or cache (for demo, we'll use a simple approach)
    # In production, store in Redis or database
    connector = ShopifyConnector(str(store_id), shop_domain)
    auth_url = connector.get_oauth_url(state_token)
    
    return {
        "auth_url": auth_url,
        "state": state_token,
    }


@router.post("/shopify/callback")
def shopify_oauth_callback(
    code: str,
    shop: str,
    state: Optional[str] = None,
    store_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Handle Shopify OAuth callback.
    
    Args:
        code: Authorization code from Shopify
        shop: Shop domain from Shopify
        state: State token for CSRF validation
        store_id: ID of store to connect
        
    Returns:
        Success message
    """
    if not store_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="store_id required")
    
    store = db.get(Store, store_id)
    if not store or store.account_id != current_user.account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    
    # TODO: Validate state token
    
    try:
        connector = ShopifyConnector(str(store_id), shop)
        token = connector.exchange_auth_code(code, connector.settings.shopify_redirect_uri, shop)
        
        # Store encrypted token in database
        encrypted_token = encrypt_secret(token.access_token)
        
        # Check if credential already exists
        existing = db.query(StoreCredential).filter_by(
            store_id=store_id,
            provider="shopify",
        ).first()
        
        if existing:
            existing.access_token = encrypted_token
            existing.refresh_token = encrypt_secret(token.refresh_token) if token.refresh_token else None
            existing.expires_at = token.expires_at
        else:
            credential = StoreCredential(
                id=uuid4(),
                store_id=store_id,
                provider="shopify",
                access_token=encrypted_token,
                refresh_token=encrypt_secret(token.refresh_token) if token.refresh_token else None,
                expires_at=token.expires_at,
            )
            db.add(credential)
        
        db.commit()
        
        return {
            "status": "success",
            "message": f"Store {store.name} connected to Shopify",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to authenticate with Shopify: {str(e)}",
        )


@router.post("/shopify/webhook/{store_id}")
async def shopify_webhook(
    store_id: UUID,
    request: Request,
    x_shopify_hmac_sha256: str = Header(None),
    x_shopify_shop_api_version: str = Header(None),
    x_shopify_topic: str = Header(None),
    db: Session = Depends(get_db),
):
    """Receive Shopify webhook.
    
    Shopify sends events like orders/create, products/update, etc.
    We validate the signature and process the event.
    
    Args:
        store_id: ID of the store
        request: HTTP request with body
        x_shopify_hmac_sha256: HMAC signature from Shopify
        x_shopify_shop_api_version: API version from Shopify
        x_shopify_topic: Event topic (e.g., "orders/create")
        
    Returns:
        Acknowledgment
    """
    # Verify store exists
    store = db.get(Store, store_id)
    if not store or store.platform != "shopify":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    
    # Get raw body for signature validation
    body = await request.body()
    body_str = body.decode("utf-8")
    
    # Validate signature
    connector = ShopifyConnector(str(store_id))
    if not connector.validate_webhook_signature(body_str, x_shopify_hmac_sha256):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")
    
    # Parse JSON
    data = json.loads(body_str)
    
    # Process based on event type
    if x_shopify_topic == "orders/create" or x_shopify_topic == "orders/updated":
        # Convert to standardized format
        order_data = connector.process_webhook(x_shopify_topic, data)
        
        # Ingest into orders table
        from app.models import orders as orders_table
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        
        order_data.pop("net_profit", None)  # generated column — Postgres computes this
        row = {"store_id": store_id, **order_data}
        stmt = pg_insert(orders_table).values([row])
        update_cols = {
            c.name: stmt.excluded[c.name]
            for c in orders_table.c
            if c.name not in ("time", "store_id", "order_id", "net_profit")
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=["store_id", "order_id", "time"],
            set_=update_cols,
        )
        db.execute(stmt)
        db.commit()
        
        return {"status": "received"}
    
    # For other event types, just acknowledge
    return {"status": "received"}


# ============================================================================
# Meta (Facebook) Ads Connectors
# ============================================================================

@router.post("/meta/auth-url")
def get_meta_auth_url(
    store_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get Meta OAuth authorization URL."""
    store = db.get(Store, store_id)
    if not store or store.account_id != current_user.account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    
    state_token = str(uuid4())
    connector = MetaConnector(str(store_id))
    auth_url = connector.get_oauth_url(state_token)
    
    return {
        "auth_url": auth_url,
        "state": state_token,
    }


@router.post("/meta/callback")
def meta_oauth_callback(
    code: str,
    store_id: Optional[UUID] = None,
    ad_account_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Handle Meta OAuth callback."""
    if not store_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="store_id required")
    
    store = db.get(Store, store_id)
    if not store or store.account_id != current_user.account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    
    try:
        connector = MetaConnector(str(store_id), ad_account_id)
        token = connector.exchange_auth_code(code, connector.settings.meta_redirect_uri)
        
        encrypted_token = encrypt_secret(token.access_token)
        
        existing = db.query(StoreCredential).filter_by(
            store_id=store_id,
            provider="meta",
        ).first()
        
        if existing:
            existing.access_token = encrypted_token
        else:
            credential = StoreCredential(
                id=uuid4(),
                store_id=store_id,
                provider="meta",
                access_token=encrypted_token,
            )
            db.add(credential)
        
        db.commit()
        
        return {
            "status": "success",
            "message": f"Store {store.name} connected to Meta",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to authenticate with Meta: {str(e)}",
        )


@router.post("/meta/sync-ad-spend")
def sync_meta_ad_spend(
    store_id: UUID,
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sync ad spend data from Meta."""
    store = db.get(Store, store_id)
    if not store or store.account_id != current_user.account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    
    # Get Meta credentials
    credential = db.query(StoreCredential).filter_by(
        store_id=store_id,
        provider="meta",
    ).first()
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Meta credentials not configured for this store",
        )
    
    try:
        access_token = decrypt_secret(credential.access_token)
        connector = MetaConnector(str(store_id))
        
        spend_records = connector.fetch_ad_spend(access_token, start_date, end_date)
        
        # Ingest into ad_spend table
        from app.models import ad_spend as ad_spend_table
        
        rows = [{"store_id": store_id, **record} for record in spend_records]
        if rows:
            db.execute(insert(ad_spend_table), rows)
            db.commit()
        
        return {
            "status": "success",
            "records_synced": len(rows),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to sync Meta ad spend: {str(e)}",
        )


# ============================================================================
# Google Ads Connectors
# ============================================================================

@router.post("/google/auth-url")
def get_google_auth_url(
    store_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get Google OAuth authorization URL."""
    store = db.get(Store, store_id)
    if not store or store.account_id != current_user.account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    
    state_token = str(uuid4())
    connector = GoogleAdsConnector(str(store_id))
    auth_url = connector.get_oauth_url(state_token)
    
    return {
        "auth_url": auth_url,
        "state": state_token,
    }


@router.post("/google/callback")
def google_oauth_callback(
    code: str,
    store_id: Optional[UUID] = None,
    customer_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Handle Google OAuth callback."""
    if not store_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="store_id required")
    
    store = db.get(Store, store_id)
    if not store or store.account_id != current_user.account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    
    try:
        connector = GoogleAdsConnector(str(store_id), customer_id)
        token = connector.exchange_auth_code(code, connector.settings.google_redirect_uri)
        
        encrypted_token = encrypt_secret(token.access_token)
        encrypted_refresh = encrypt_secret(token.refresh_token) if token.refresh_token else None
        
        existing = db.query(StoreCredential).filter_by(
            store_id=store_id,
            provider="google",
        ).first()
        
        if existing:
            existing.access_token = encrypted_token
            existing.refresh_token = encrypted_refresh
            existing.expires_at = token.expires_at
        else:
            credential = StoreCredential(
                id=uuid4(),
                store_id=store_id,
                provider="google",
                access_token=encrypted_token,
                refresh_token=encrypted_refresh,
                expires_at=token.expires_at,
            )
            db.add(credential)
        
        db.commit()
        
        return {
            "status": "success",
            "message": f"Store {store.name} connected to Google Ads",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to authenticate with Google: {str(e)}",
        )


@router.post("/google/sync-ad-spend")
def sync_google_ad_spend(
    store_id: UUID,
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sync ad spend data from Google Ads."""
    store = db.get(Store, store_id)
    if not store or store.account_id != current_user.account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    
    # Get Google credentials
    credential = db.query(StoreCredential).filter_by(
        store_id=store_id,
        provider="google",
    ).first()
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google credentials not configured for this store",
        )
    
    try:
        access_token = decrypt_secret(credential.access_token)
        
        # Check if token is expired and refresh if needed
        if credential.expires_at and datetime.utcnow() > credential.expires_at:
            refresh_token = decrypt_secret(credential.refresh_token) if credential.refresh_token else None
            if refresh_token:
                connector = GoogleAdsConnector(str(store_id))
                new_token = connector.refresh_access_token(refresh_token)
                access_token = new_token.access_token
                credential.access_token = encrypt_secret(access_token)
                credential.expires_at = new_token.expires_at
                db.commit()
        
        connector = GoogleAdsConnector(str(store_id))
        spend_records = connector.fetch_ad_spend(access_token, start_date, end_date)
        
        # Ingest into ad_spend table
        from app.models import ad_spend as ad_spend_table
        
        rows = [{"store_id": store_id, **record} for record in spend_records]
        if rows:
            db.execute(insert(ad_spend_table), rows)
            db.commit()
        
        return {
            "status": "success",
            "records_synced": len(rows),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to sync Google ad spend: {str(e)}",
        )
