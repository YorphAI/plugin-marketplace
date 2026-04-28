-- yorph-taggy schema. Two tables. That's the entire data model.
--
-- Comments, sub-tasks, epic children, doc pages → items with parent set.
-- Status, assignment, priority, points, sprint, release, labels → tag rows.
-- Removing a tag is a soft-delete: row stays, removed_at gets set.
-- Custom concepts (severity, customer, RICE, OKR) → new tag prefixes, no DDL.

CREATE SEQUENCE IF NOT EXISTS items_key_seq;

CREATE TABLE IF NOT EXISTS items (
  key         TEXT PRIMARY KEY DEFAULT nextval('items_key_seq')::text,
  title       TEXT NOT NULL,
  body        TEXT,
  parent      TEXT REFERENCES items(key) ON DELETE CASCADE,
  created_by  TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tags (
  id          BIGSERIAL PRIMARY KEY,
  item        TEXT NOT NULL REFERENCES items(key) ON DELETE CASCADE,
  tag         TEXT NOT NULL,
  tagged_by   TEXT NOT NULL,
  tagged_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  removed_by  TEXT,
  removed_at  TIMESTAMPTZ
);

-- An item can carry the same tag many times across history, but only one
-- copy may be *active* (removed_at IS NULL) at any moment. Re-tagging after
-- a removal preserves both the old (removed) row and the new active row.
CREATE UNIQUE INDEX IF NOT EXISTS tags_active_unique
  ON tags(item, tag) WHERE removed_at IS NULL;

CREATE INDEX IF NOT EXISTS tags_tag_idx ON tags(tag);
CREATE INDEX IF NOT EXISTS tags_history_idx ON tags(item, tag, tagged_at);

-- Touch updated_at on item edits.
CREATE OR REPLACE FUNCTION items_set_updated_at() RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS items_touch_updated_at ON items;
CREATE TRIGGER items_touch_updated_at
  BEFORE UPDATE ON items
  FOR EACH ROW EXECUTE FUNCTION items_set_updated_at();
