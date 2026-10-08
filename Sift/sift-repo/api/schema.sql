CREATE TABLE IF NOT EXISTS audits (
  id TEXT PRIMARY KEY,
  url TEXT NOT NULL,
  score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
  result TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_audits_created ON audits(created_at);
CREATE TABLE IF NOT EXISTS waitlist (
  email TEXT PRIMARY KEY,
  created_at INTEGER NOT NULL
);
