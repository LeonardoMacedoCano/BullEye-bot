import sqlite3
import time
from bot.db.database import get_connection


def get_or_create_user(discord_id: str) -> sqlite3.Row:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (discord_id) VALUES (?)", (discord_id,))
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE discord_id = ?", (discord_id,))
        return cursor.fetchone()
    finally:
        conn.close()


def add_ticker(user_id: int, ticker: str, category: str, subcategory: str | None = None) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO tickers (user_id, ticker, category, subcategory) VALUES (?, ?, ?, ?)",
            (user_id, ticker.upper(), category, subcategory),
        )
        conn.commit()
    finally:
        conn.close()


def remove_ticker(user_id: int, ticker: str) -> int:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM tickers WHERE user_id = ? AND ticker = ?",
            (user_id, ticker.upper()),
        )
        conn.execute(
            "UPDATE alerts SET active = 0 WHERE user_id = ? AND ticker = ?",
            (user_id, ticker.upper()),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def list_tickers(user_id: int) -> list[sqlite3.Row]:
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT * FROM tickers WHERE user_id = ? ORDER BY category, ticker",
            (user_id,),
        )
        return cursor.fetchall()
    finally:
        conn.close()


def get_ticker_row(user_id: int, ticker: str) -> sqlite3.Row | None:
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT * FROM tickers WHERE user_id = ? AND ticker = ?",
            (user_id, ticker.upper()),
        )
        return cursor.fetchone()
    finally:
        conn.close()


def set_user_ceiling(user_id: int, ticker: str, ceiling: float) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE tickers SET user_ceiling = ? WHERE user_id = ? AND ticker = ?",
            (ceiling, user_id, ticker.upper()),
        )
        conn.commit()
    finally:
        conn.close()


def clear_user_ceiling(user_id: int, ticker: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE tickers SET user_ceiling = NULL WHERE user_id = ? AND ticker = ?",
            (user_id, ticker.upper()),
        )
        conn.commit()
    finally:
        conn.close()


def update_ticker_subcategory(user_id: int, ticker: str, subcategory: str | None) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE tickers SET subcategory = ? WHERE user_id = ? AND ticker = ?",
            (subcategory, user_id, ticker.upper()),
        )
        conn.commit()
    finally:
        conn.close()


def get_ticker_category(user_id: int, ticker: str) -> str | None:
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT category FROM tickers WHERE user_id = ? AND ticker = ?",
            (user_id, ticker.upper()),
        )
        row = cursor.fetchone()
        return row["category"] if row else None
    finally:
        conn.close()


def ticker_exists(user_id: int, ticker: str) -> bool:
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT 1 FROM tickers WHERE user_id = ? AND ticker = ?",
            (user_id, ticker.upper()),
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def add_alert(user_id: int, ticker: str, target_price: float) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO alerts (user_id, ticker, target_price) VALUES (?, ?, ?)",
            (user_id, ticker.upper(), target_price),
        )
        conn.commit()
    finally:
        conn.close()


def get_active_alerts(user_id: int | None = None) -> list[sqlite3.Row]:
    conn = get_connection()
    try:
        if user_id is not None:
            cursor = conn.execute(
                "SELECT a.*, u.discord_id FROM alerts a JOIN users u ON a.user_id = u.id "
                "WHERE a.active = 1 AND a.user_id = ?",
                (user_id,),
            )
        else:
            cursor = conn.execute(
                "SELECT a.*, u.discord_id FROM alerts a JOIN users u ON a.user_id = u.id "
                "WHERE a.active = 1"
            )
        return cursor.fetchall()
    finally:
        conn.close()


def deactivate_alert(alert_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("UPDATE alerts SET active = 0 WHERE id = ?", (alert_id,))
        conn.commit()
    finally:
        conn.close()


def set_schedule(user_id: int, time: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO schedules (user_id, time, active) VALUES (?, ?, 1) "
            "ON CONFLICT(user_id) DO UPDATE SET time = excluded.time, active = 1",
            (user_id, time),
        )
        conn.commit()
    finally:
        conn.close()


def get_schedule(user_id: int) -> sqlite3.Row | None:
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT * FROM schedules WHERE user_id = ? AND active = 1", (user_id,)
        )
        return cursor.fetchone()
    finally:
        conn.close()


def deactivate_schedule(user_id: int) -> int:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE schedules SET active = 0 WHERE user_id = ? AND active = 1", (user_id,)
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def get_ticker_cache(ticker: str) -> sqlite3.Row | None:
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT * FROM ticker_cache WHERE ticker = ?", (ticker.upper(),)
        )
        return cursor.fetchone()
    finally:
        conn.close()


def set_ticker_cache(ticker: str, dy_rate: float, dy_yield: float) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO ticker_cache (ticker, dy_rate, dy_yield, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (ticker.upper(), dy_rate, dy_yield, int(time.time())),
        )
        conn.commit()
    finally:
        conn.close()


def get_all_active_schedules() -> list[sqlite3.Row]:
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT s.*, u.discord_id FROM schedules s JOIN users u ON s.user_id = u.id "
            "WHERE s.active = 1"
        )
        return cursor.fetchall()
    finally:
        conn.close()


def update_last_sent_date(user_id: int, date_str: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE schedules SET last_sent_date = ? WHERE user_id = ? AND active = 1",
            (date_str, user_id),
        )
        conn.commit()
    finally:
        conn.close()
