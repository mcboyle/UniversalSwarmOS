CREATE TABLE IF NOT EXISTS cursors (
                seat TEXT NOT NULL,
                topic TEXT NOT NULL,
                last_read_id INTEGER NOT NULL,
                PRIMARY KEY (seat, topic)
            );

CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                payload TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
