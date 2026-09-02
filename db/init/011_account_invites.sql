CREATE TABLE account_invites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('owner', 'admin', 'viewer')),
    invited_by UUID REFERENCES users(id) ON DELETE SET NULL,
    token_hash VARCHAR(64) NOT NULL UNIQUE,  -- sha256 hex of the raw token; raw token only ever lives in the response, never at rest
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'revoked')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    accepted_at TIMESTAMPTZ
);

-- Prevent duplicate pending invites to the same email within an account.
CREATE UNIQUE INDEX uq_account_invites_pending ON account_invites(account_id, email)
    WHERE status = 'pending';
