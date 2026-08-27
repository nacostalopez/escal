from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import accounts, stores, products, orders, pixel_events, ad_spend, metrics

app = FastAPI(title="Escal", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(accounts.router)
app.include_router(stores.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(pixel_events.router)
app.include_router(ad_spend.router)
app.include_router(metrics.router)


@app.get("/health")
def health():
    return {"status": "ok"}
