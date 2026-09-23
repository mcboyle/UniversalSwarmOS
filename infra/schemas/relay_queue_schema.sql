CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target TEXT NOT NULL,
                    sender TEXT DEFAULT 'unknown',
                    payload TEXT NOT NULL,
                    priority TEXT DEFAULT 'normal',
                    queued_at TEXT NOT NULL,
                    status TEXT DEFAULT 'pending'
                );

CREATE INDEX IF NOT EXISTS idx_messages_target_status
                ON messages(target, status);
