-- Per-store role override — additive on top of the account-wide User.role.
-- A row here overrides the effective role for that one store; no row means
-- the account role applies (today's behavior, unchanged). See
-- app/dependencies.py::require_store_role.
CREATE TABLE store_memberships (
    store_id UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('owner', 'admin', 'viewer')),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (store_id, user_id)
);
