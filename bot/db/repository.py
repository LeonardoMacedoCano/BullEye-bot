import sqlite3
import time
from bot.db.database import connection


def get_or_create_user(discord_id: str) -> sqlite3.Row:
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (discord_id) VALUES (?)", (discord_id,))
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE discord_id = ?", (discord_id,))
        return cursor.fetchone()


def upsert_ticker(
    symbol: str,
    subcategory: str | None = None,
    quote_type: str | None = None,
    sector: str | None = None,
    industry: str | None = None,
) -> int:
    with connection() as conn:
        conn.execute(
            "INSERT INTO tickers (symbol, subcategory, quote_type, sector, industry) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(symbol) DO UPDATE SET "
            "subcategory = COALESCE(excluded.subcategory, subcategory), "
            "quote_type = COALESCE(excluded.quote_type, quote_type), "
            "sector = COALESCE(excluded.sector, sector), "
            "industry = COALESCE(excluded.industry, industry)",
            (symbol.upper(), subcategory, quote_type, sector, industry),
        )
        conn.commit()
        row = conn.execute("SELECT id FROM tickers WHERE symbol = ?", (symbol.upper(),)).fetchone()
        return row["id"]


def add_ticker(
    user_id: int,
    ticker: str,
    category: str,
    subcategory: str | None = None,
    sector: str | None = None,
    industry: str | None = None,
) -> None:
    with connection() as conn:
        conn.execute(
            "INSERT INTO tickers (symbol, subcategory, sector, industry) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(symbol) DO UPDATE SET "
            "subcategory = COALESCE(excluded.subcategory, subcategory), "
            "sector = COALESCE(excluded.sector, sector), "
            "industry = COALESCE(excluded.industry, industry)",
            (ticker.upper(), subcategory, sector, industry),
        )
        conn.commit()
        t_row = conn.execute("SELECT id FROM tickers WHERE symbol = ?", (ticker.upper(),)).fetchone()
        conn.execute(
            "INSERT OR IGNORE INTO user_tickers (user_id, ticker_id, category) VALUES (?, ?, ?)",
            (user_id, t_row["id"], category),
        )
        conn.commit()


def remove_ticker(user_id: int, ticker: str) -> int:
    with connection() as conn:
        cursor = conn.cursor()
        t_row = cursor.execute(
            "SELECT id FROM tickers WHERE symbol = ?", (ticker.upper(),)
        ).fetchone()
        if not t_row:
            return 0
        ticker_id = t_row["id"]
        cursor.execute(
            "DELETE FROM user_tickers WHERE user_id = ? AND ticker_id = ?",
            (user_id, ticker_id),
        )
        count = cursor.rowcount
        cursor.execute(
            "UPDATE alerts SET active = 0 WHERE user_id = ? AND ticker_id = ?",
            (user_id, ticker_id),
        )
        conn.commit()
        return count


def list_tickers(user_id: int) -> list[sqlite3.Row]:
    with connection() as conn:
        cursor = conn.execute(
            "SELECT t.symbol AS ticker, ut.category, t.subcategory, t.sector, t.industry, "
            "ut.user_ceiling, ut.note, MIN(a.target_price) AS alert_price "
            "FROM user_tickers ut JOIN tickers t ON ut.ticker_id = t.id "
            "LEFT JOIN alerts a ON a.user_id = ut.user_id AND a.ticker_id = ut.ticker_id AND a.active = 1 "
            "WHERE ut.user_id = ? GROUP BY ut.id ORDER BY ut.category, t.symbol",
            (user_id,),
        )
        return cursor.fetchall()


def get_ticker_row(user_id: int, ticker: str) -> sqlite3.Row | None:
    with connection() as conn:
        cursor = conn.execute(
            "SELECT t.symbol AS ticker, ut.category, t.subcategory, ut.user_ceiling, ut.note "
            "FROM user_tickers ut JOIN tickers t ON ut.ticker_id = t.id "
            "WHERE ut.user_id = ? AND t.symbol = ?",
            (user_id, ticker.upper()),
        )
        return cursor.fetchone()


def set_user_ceiling(user_id: int, ticker: str, ceiling: float) -> None:
    with connection() as conn:
        conn.execute(
            "UPDATE user_tickers SET user_ceiling = ? "
            "WHERE user_id = ? AND ticker_id = (SELECT id FROM tickers WHERE symbol = ?)",
            (ceiling, user_id, ticker.upper()),
        )
        conn.commit()


def clear_user_ceiling(user_id: int, ticker: str) -> None:
    with connection() as conn:
        conn.execute(
            "UPDATE user_tickers SET user_ceiling = NULL "
            "WHERE user_id = ? AND ticker_id = (SELECT id FROM tickers WHERE symbol = ?)",
            (user_id, ticker.upper()),
        )
        conn.commit()


def set_user_note(user_id: int, ticker: str, note: str) -> None:
    with connection() as conn:
        conn.execute(
            "UPDATE user_tickers SET note = ? "
            "WHERE user_id = ? AND ticker_id = (SELECT id FROM tickers WHERE symbol = ?)",
            (note, user_id, ticker.upper()),
        )
        conn.commit()


def clear_user_note(user_id: int, ticker: str) -> None:
    with connection() as conn:
        conn.execute(
            "UPDATE user_tickers SET note = NULL "
            "WHERE user_id = ? AND ticker_id = (SELECT id FROM tickers WHERE symbol = ?)",
            (user_id, ticker.upper()),
        )
        conn.commit()


def update_ticker_subcategory(user_id: int, ticker: str, subcategory: str | None) -> None:
    with connection() as conn:
        conn.execute(
            "UPDATE tickers SET subcategory = ? WHERE symbol = ?",
            (subcategory, ticker.upper()),
        )
        conn.commit()


def update_ticker_sector_industry(ticker: str, sector: str | None, industry: str | None) -> None:
    with connection() as conn:
        conn.execute(
            "UPDATE tickers SET sector = ?, industry = ? WHERE symbol = ?",
            (sector, industry, ticker.upper()),
        )
        conn.commit()


def get_ticker_category(user_id: int, ticker: str) -> str | None:
    with connection() as conn:
        cursor = conn.execute(
            "SELECT ut.category FROM user_tickers ut JOIN tickers t ON ut.ticker_id = t.id "
            "WHERE ut.user_id = ? AND t.symbol = ?",
            (user_id, ticker.upper()),
        )
        row = cursor.fetchone()
        return row["category"] if row else None


def ticker_exists(user_id: int, ticker: str) -> bool:
    with connection() as conn:
        cursor = conn.execute(
            "SELECT 1 FROM user_tickers ut JOIN tickers t ON ut.ticker_id = t.id "
            "WHERE ut.user_id = ? AND t.symbol = ?",
            (user_id, ticker.upper()),
        )
        return cursor.fetchone() is not None


def add_alert(user_id: int, ticker: str, target_price: float) -> None:
    with connection() as conn:
        t_row = conn.execute(
            "SELECT id FROM tickers WHERE symbol = ?", (ticker.upper(),)
        ).fetchone()
        if not t_row:
            return
        conn.execute(
            "INSERT INTO alerts (user_id, ticker_id, target_price) VALUES (?, ?, ?)",
            (user_id, t_row["id"], target_price),
        )
        conn.commit()


def get_active_alerts(user_id: int | None = None) -> list[sqlite3.Row]:
    with connection() as conn:
        if user_id is not None:
            cursor = conn.execute(
                "SELECT a.*, u.discord_id, t.symbol AS ticker "
                "FROM alerts a JOIN users u ON a.user_id = u.id "
                "JOIN tickers t ON a.ticker_id = t.id "
                "WHERE a.active = 1 AND a.user_id = ?",
                (user_id,),
            )
        else:
            cursor = conn.execute(
                "SELECT a.*, u.discord_id, t.symbol AS ticker "
                "FROM alerts a JOIN users u ON a.user_id = u.id "
                "JOIN tickers t ON a.ticker_id = t.id "
                "WHERE a.active = 1"
            )
        return cursor.fetchall()


def deactivate_alert(alert_id: int) -> None:
    with connection() as conn:
        conn.execute("UPDATE alerts SET active = 0 WHERE id = ?", (alert_id,))
        conn.commit()


def set_schedule(user_id: int, time: str) -> None:
    with connection() as conn:
        conn.execute(
            "INSERT INTO schedules (user_id, time, active) VALUES (?, ?, 1) "
            "ON CONFLICT(user_id) DO UPDATE SET time = excluded.time, active = 1",
            (user_id, time),
        )
        conn.commit()


def get_schedule(user_id: int) -> sqlite3.Row | None:
    with connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM schedules WHERE user_id = ? AND active = 1", (user_id,)
        )
        return cursor.fetchone()


def deactivate_schedule(user_id: int) -> int:
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE schedules SET active = 0 WHERE user_id = ? AND active = 1", (user_id,)
        )
        conn.commit()
        return cursor.rowcount


def get_all_active_schedules() -> list[sqlite3.Row]:
    with connection() as conn:
        cursor = conn.execute(
            "SELECT s.*, u.discord_id FROM schedules s JOIN users u ON s.user_id = u.id "
            "WHERE s.active = 1"
        )
        return cursor.fetchall()


def update_last_sent_date(user_id: int, date_str: str) -> None:
    with connection() as conn:
        conn.execute(
            "UPDATE schedules SET last_sent_date = ? WHERE user_id = ? AND active = 1",
            (date_str, user_id),
        )
        conn.commit()


def get_price_cache(ticker: str) -> sqlite3.Row | None:
    with connection() as conn:
        cursor = conn.execute(
            "SELECT pc.* FROM ticker_price_cache pc JOIN tickers t ON pc.ticker_id = t.id "
            "WHERE t.symbol = ?",
            (ticker.upper(),),
        )
        return cursor.fetchone()


def set_price_cache(ticker: str, dy_rate: float, dy_yield: float) -> None:
    with connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO tickers (symbol) VALUES (?)", (ticker.upper(),)
        )
        conn.commit()
        t_row = conn.execute("SELECT id FROM tickers WHERE symbol = ?", (ticker.upper(),)).fetchone()
        conn.execute(
            "INSERT OR REPLACE INTO ticker_price_cache (ticker_id, dy_rate, dy_yield, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (t_row["id"], dy_rate, dy_yield, int(time.time())),
        )
        conn.commit()


def clear_price_cache_db_for_tickers(symbols: list[str]) -> int:
    if not symbols:
        return 0
    upper = [s.upper() for s in symbols]
    placeholders = ",".join("?" * len(upper))
    with connection() as conn:
        cursor = conn.execute(
            f"DELETE FROM ticker_price_cache WHERE ticker_id IN "
            f"(SELECT id FROM tickers WHERE symbol IN ({placeholders}))",
            upper,
        )
        conn.commit()
        return cursor.rowcount


def upsert_provento(
    ticker_id: int,
    ex_date: str,
    pay_date: str | None,
    amount: float | None,
    ptype: str | None,
    description: str | None,
) -> None:
    with connection() as conn:
        conn.execute(
            "INSERT INTO proventos (ticker_id, ex_date, pay_date, amount, type, description, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(ticker_id, ex_date, type) DO UPDATE SET "
            "pay_date = excluded.pay_date, amount = excluded.amount, "
            "description = excluded.description, updated_at = excluded.updated_at",
            (ticker_id, ex_date, pay_date, amount, ptype, description, int(time.time())),
        )
        conn.commit()


def get_proventos_for_ticker(ticker_id: int) -> list[sqlite3.Row]:
    with connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM proventos WHERE ticker_id = ? ORDER BY ex_date DESC LIMIT 10",
            (ticker_id,),
        )
        return cursor.fetchall()


def clear_proventos_for_tickers(symbols: list[str]) -> int:
    if not symbols:
        return 0
    upper = [s.upper() for s in symbols]
    placeholders = ",".join("?" * len(upper))
    with connection() as conn:
        cursor = conn.execute(
            f"DELETE FROM proventos WHERE ticker_id IN "
            f"(SELECT id FROM tickers WHERE symbol IN ({placeholders}))",
            upper,
        )
        conn.commit()
        return cursor.rowcount


def set_user_fgi_ceiling(user_id: int, value: int) -> None:
    with connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO user_fgi_ceilings (user_id, ceiling_value) VALUES (?, ?)",
            (user_id, value),
        )
        conn.commit()


def clear_user_fgi_ceiling(user_id: int) -> None:
    with connection() as conn:
        conn.execute("DELETE FROM user_fgi_ceilings WHERE user_id = ?", (user_id,))
        conn.commit()


def get_user_fgi_ceiling(user_id: int) -> int | None:
    with connection() as conn:
        row = conn.execute(
            "SELECT ceiling_value FROM user_fgi_ceilings WHERE user_id = ?", (user_id,)
        ).fetchone()
        return int(row["ceiling_value"]) if row else None


def add_fgi_alert(user_id: int, target_value: int) -> None:
    with connection() as conn:
        conn.execute(
            "INSERT INTO fgi_alerts (user_id, target_value) VALUES (?, ?)",
            (user_id, target_value),
        )
        conn.commit()


def get_active_fgi_alerts() -> list[sqlite3.Row]:
    with connection() as conn:
        cursor = conn.execute(
            "SELECT fa.*, u.discord_id FROM fgi_alerts fa JOIN users u ON fa.user_id = u.id "
            "WHERE fa.active = 1"
        )
        return cursor.fetchall()


def deactivate_fgi_alert(alert_id: int) -> None:
    with connection() as conn:
        conn.execute("UPDATE fgi_alerts SET active = 0 WHERE id = ?", (alert_id,))
        conn.commit()


def get_proventos_upcoming(symbols: list[str], days: int = 60) -> list[sqlite3.Row]:
    from datetime import date, timedelta
    today = date.today().isoformat()
    limit = (date.today() + timedelta(days=days)).isoformat()
    upper = [s.upper() for s in symbols]
    if not upper:
        return []
    placeholders = ",".join("?" * len(upper))
    with connection() as conn:
        cursor = conn.execute(
            f"SELECT t.symbol, p.ex_date, p.pay_date, p.amount, p.type "
            f"FROM proventos p JOIN tickers t ON p.ticker_id = t.id "
            f"WHERE t.symbol IN ({placeholders}) "
            f"AND p.ex_date IS NOT NULL "
            f"AND p.ex_date >= ? AND p.ex_date <= ? "
            f"ORDER BY p.ex_date, t.symbol",
            (*upper, today, limit),
        )
        return cursor.fetchall()
