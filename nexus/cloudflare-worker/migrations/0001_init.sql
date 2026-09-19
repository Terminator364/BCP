CREATE TABLE IF NOT EXISTS commands (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  telegram_update_id INTEGER NOT NULL UNIQUE,
  chat_id TEXT NOT NULL,
  text TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'QUEUED',
  created_at TEXT NOT NULL,
  delivered_at TEXT,
  replied_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_commands_state_id ON commands(state, id);

CREATE TABLE IF NOT EXISTS replies (
  command_id INTEGER PRIMARY KEY,
  idempotency_key TEXT NOT NULL UNIQUE,
  body_hash TEXT NOT NULL,
  status TEXT NOT NULL,
  telegram_message_id TEXT,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(command_id) REFERENCES commands(id)
);

CREATE TABLE IF NOT EXISTS outbound (
  idempotency_key TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  body_hash TEXT NOT NULL,
  status TEXT NOT NULL,
  telegram_message_id TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS live_cards (
  card_key TEXT PRIMARY KEY,
  telegram_message_id TEXT NOT NULL,
  body_hash TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
  report_key TEXT PRIMARY KEY,
  body_text TEXT NOT NULL,
  body_hash TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
