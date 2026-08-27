"""Populate a running Escal API (default http://localhost:8000) with demo
data so you can immediately see revenue, ad spend and True ROAS.

Usage:
    python scripts/seed_demo.py
"""

import random
from datetime import datetime, timedelta, timezone

import requests

BASE_URL = "http://localhost:8000"


def main():
    account = requests.post(f"{BASE_URL}/accounts", json={"name": "Demo Account"}).json()
    print("account:", account["id"])

    store = requests.post(
        f"{BASE_URL}/stores",
        json={
            "account_id": account["id"],
            "name": "Demo Store",
            "platform": "shopify",
            "currency": "USD",
            "timezone": "UTC",
        },
    ).json()
    store_id = store["id"]
    print("store:", store_id)

    products = requests.put(
        f"{BASE_URL}/stores/{store_id}/products",
        json=[
            {"external_id": "sku-1", "sku": "SKU1", "title": "T-Shirt", "cogs": 5.0, "shipping_cost": 2.0},
            {"external_id": "sku-2", "sku": "SKU2", "title": "Hoodie", "cogs": 12.0, "shipping_cost": 3.0},
        ],
    ).json()
    print("products:", [p["title"] for p in products])

    now = datetime.now(timezone.utc)
    orders = []
    for day_offset in range(14):
        day = now - timedelta(days=day_offset)
        for _ in range(random.randint(3, 10)):
            gross = round(random.uniform(20, 150), 2)
            cogs = round(gross * 0.25, 2)
            orders.append(
                {
                    "time": (day - timedelta(hours=random.randint(0, 23))).isoformat(),
                    "order_id": f"order-{day_offset}-{random.randint(1000, 9999)}",
                    "gross_amount": gross,
                    "discounts": 0.0,
                    "shipping_fee": 4.99,
                    "payment_gateway_fee": round(gross * 0.029 + 0.30, 2),
                    "cogs_total": cogs,
                    "currency": "USD",
                    "attribution_utm_source": random.choice(["meta", "google", "organic"]),
                    "attribution_utm_campaign": "demo-campaign",
                }
            )
    r = requests.post(f"{BASE_URL}/stores/{store_id}/orders", json=orders)
    print("orders inserted:", r.json())

    ad_spend = []
    for day_offset in range(14):
        day = now - timedelta(days=day_offset)
        for platform in ("meta", "google"):
            ad_spend.append(
                {
                    "time": day.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
                    "platform": platform,
                    "campaign_id": f"{platform}-demo-campaign",
                    "campaign_name": "Demo Campaign",
                    "adset_id": "adset-1",
                    "spend": round(random.uniform(20, 80), 2),
                    "impressions": random.randint(1000, 5000),
                    "clicks": random.randint(50, 300),
                }
            )
    r = requests.post(f"{BASE_URL}/stores/{store_id}/ad-spend", json=ad_spend)
    print("ad spend inserted:", r.json())

    start = (now - timedelta(days=14)).isoformat()
    end = now.isoformat()
    summary = requests.get(
        f"{BASE_URL}/stores/{store_id}/metrics/summary",
        params={"start": start, "end": end},
    ).json()
    print("\nSummary (last 14 days):")
    print(summary)
    print(f"\nTry it yourself: GET {BASE_URL}/stores/{store_id}/metrics/summary?start={start}&end={end}")


if __name__ == "__main__":
    main()
