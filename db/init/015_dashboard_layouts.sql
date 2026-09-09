-- One row per user: their chosen dashboard widgets, order, and which stat
-- widget (if any) is the 2x2 "hero" tile. No row yet = the default layout
-- (every widget, True ROAS as hero) — see app/routes/dashboard.py.
CREATE TABLE dashboard_layouts (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    widgets JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
