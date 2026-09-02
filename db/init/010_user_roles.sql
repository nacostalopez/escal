-- Every existing row today is the sole user of its account (register always
-- creates a fresh account 1:1 with its first user, and no invite/join flow
-- has ever existed), so backfilling every existing row to 'owner' is correct.
-- Going forward the app always sets role explicitly at creation time
-- (register -> 'owner', invite-accept -> the invited role), so the column
-- keeps its NOT NULL/CHECK constraint but the backfill DEFAULT is dropped
-- after use to make that explicit at the schema level.
ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'owner'
    CHECK (role IN ('owner', 'admin', 'viewer'));
ALTER TABLE users ALTER COLUMN role DROP DEFAULT;
