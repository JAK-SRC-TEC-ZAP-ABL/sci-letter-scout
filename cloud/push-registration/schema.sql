CREATE TABLE IF NOT EXISTS devices (
  id TEXT PRIMARY KEY,
  specialty TEXT NOT NULL,
  token_iv TEXT NOT NULL,
  token_ciphertext TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
