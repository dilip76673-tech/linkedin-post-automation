import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "scheduled_posts.db"


def get_connection():
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                caption TEXT NOT NULL,
                scheduled_time TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                image_url TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                error_message TEXT
            )
        """)
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(scheduled_posts)")
        }
        migrations = {
            "image_url": "ALTER TABLE scheduled_posts ADD COLUMN image_url TEXT",
            "created_at": "ALTER TABLE scheduled_posts ADD COLUMN created_at TEXT",
            "error_message": "ALTER TABLE scheduled_posts ADD COLUMN error_message TEXT",
        }
        for name, sql in migrations.items():
            if name not in columns:
                connection.execute(sql)


def add_scheduled_post(caption, scheduled_time, image_url):
    init_db()
    with get_connection() as connection:
        cursor = connection.execute(
            """INSERT INTO scheduled_posts
               (caption, scheduled_time, status, image_url)
               VALUES (?, ?, 'pending', ?)""",
            (caption, scheduled_time, image_url),
        )
        return cursor.lastrowid


def list_scheduled_posts(limit=50):
    init_db()
    with get_connection() as connection:
        rows = connection.execute(
            """SELECT id, caption, scheduled_time, status, image_url, error_message
               FROM scheduled_posts
               ORDER BY scheduled_time DESC, id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
