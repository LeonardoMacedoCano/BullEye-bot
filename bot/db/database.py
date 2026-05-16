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
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id TEXT    UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tickers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol      TEXT    UNIQUE NOT NULL,
                subcategory TEXT    DEFAULT NULL,
                quote_type  TEXT    DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS user_tickers (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL REFERENCES users(id),
                ticker_id    INTEGER NOT NULL REFERENCES tickers(id),
                category     TEXT    NOT NULL CHECK(category IN ('wallet', 'watchlist')),
                user_ceiling REAL    DEFAULT NULL,
                note         TEXT    DEFAULT NULL,
                UNIQUE(user_id, ticker_id)
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL REFERENCES users(id),
                ticker_id    INTEGER NOT NULL REFERENCES tickers(id),
                target_price REAL    NOT NULL,
                active       INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS schedules (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id        INTEGER NOT NULL UNIQUE REFERENCES users(id),
                time           TEXT    NOT NULL,
                active         INTEGER NOT NULL DEFAULT 1,
                last_sent_date TEXT    DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS ticker_price_cache (
                ticker_id  INTEGER PRIMARY KEY REFERENCES tickers(id),
                dy_rate    REAL,
                dy_yield   REAL,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS proventos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker_id   INTEGER NOT NULL REFERENCES tickers(id),
                ex_date     TEXT    NOT NULL,
                pay_date    TEXT    DEFAULT NULL,
                amount      REAL    DEFAULT NULL,
                type        TEXT    DEFAULT NULL,
                description TEXT    DEFAULT NULL,
                updated_at  INTEGER NOT NULL,
                UNIQUE(ticker_id, ex_date, type)
            );
        """)
        logger.info("Database initialized at %s", DATABASE_PATH)
    finally:
        conn.close()
