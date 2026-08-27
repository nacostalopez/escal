-- 1. Usuarios / Cuentas
CREATE TABLE accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Tiendas e Integraciones
CREATE TABLE stores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID REFERENCES accounts(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    platform VARCHAR(50) NOT NULL, -- 'shopify', 'tiendanube', 'mercadolibre'
    currency VARCHAR(3) DEFAULT 'USD',
    timezone VARCHAR(50) DEFAULT 'UTC',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tokens de integracion (OAuth)
CREATE TABLE store_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id UUID REFERENCES stores(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL, -- 'facebook_ads', 'google_ads', 'mercadopago'
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TIMESTAMPTZ,
    UNIQUE(store_id, provider)
);

-- 3. Catalogo de Productos y COGS
CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id UUID REFERENCES stores(id) ON DELETE CASCADE,
    external_id VARCHAR(255) NOT NULL,
    sku VARCHAR(100),
    title VARCHAR(255) NOT NULL,
    cogs NUMERIC(12, 4) DEFAULT 0.0,
    shipping_cost NUMERIC(12, 4) DEFAULT 0.0,
    UNIQUE(store_id, external_id)
);
