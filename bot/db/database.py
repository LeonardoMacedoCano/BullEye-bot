import os
import sqlite3
import logging

logger = logging.getLogger(__name__)

DATABASE_PATH = os.getenv("DATABASE_PATH") or "/data/bot.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id TEXT    UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tickers (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER NOT NULL REFERENCES users(id),
                ticker    TEXT    NOT NULL,
                category  TEXT    NOT NULL CHECK(category IN ('wallet', 'watchlist'))
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL REFERENCES users(id),
                ticker       TEXT    NOT NULL,
                target_price REAL    NOT NULL,
                active       INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS schedules (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
                time    TEXT    NOT NULL,
                active  INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS ticker_cache (
                ticker      TEXT    PRIMARY KEY,
                dy_rate     REAL,
                dy_yield    REAL,
                eps         REAL,
                book_value  REAL,
                updated_at  INTEGER NOT NULL
            );
        """)
        conn.commit()
        try:
            conn.execute("ALTER TABLE tickers ADD COLUMN subcategory TEXT DEFAULT NULL")
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE tickers ADD COLUMN user_teto REAL DEFAULT NULL")
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE tickers RENAME COLUMN user_teto TO user_ceiling")
            conn.commit()
        except Exception:
            pass
        logger.info("Database initialized at %s", DATABASE_PATH)
    finally:
        conn.close()
