from bot.services.market import SUBCATEGORY_LABELS, SUBCATEGORY_ORDER
from bot.shared.formatting import display_name, currency, render_table, group_by_subcategory


def _fmt_price(price: float | None, ticker: str) -> str:
    if price is None:
        return "—"
    sym = currency(ticker)
    return f"{sym}{price:,.2f}"


def _truncate_note(note: str | None, max_len: int = 80) -> str:
    if not note:
        return "—"
    return note if len(note) <= max_len else note[:max_len - 1] + "…"


def _fmt_sector(row) -> str:
    s = row["sector"] or ""
    i = row["industry"] or ""
    combined = f"{s} / {i}" if s and i else s or i
    return combined or "—"


def _get_details(group_rows: list) -> list[str]:
    """Free-text (sector/note) per ticker, kept out of the fixed-width table so long
    values don't break column alignment — rendered as prose lines instead."""
    details = []
    for row in group_rows:
        parts = [p for p in (_fmt_sector(row), _truncate_note(row["note"])) if p != "—"]
        if parts:
            details.append(f"**{display_name(row['ticker'])}** — " + " · ".join(parts))
    return details


def get_ticker_groups(rows: list) -> list[dict]:
    groups = group_by_subcategory(rows, SUBCATEGORY_ORDER)
    if not (len(groups) > 1 or (len(groups) == 1 and groups[0][0] is not None)):
        groups = [(None, rows)]

    result = []
    for key, group_rows in groups:
        label = SUBCATEGORY_LABELS.get(key, key) if key else None
        headers = ["Ticker", "Ceiling", "Alert"]
        data_rows = [
            [
                display_name(row["ticker"]),
                _fmt_price(row["user_ceiling"], row["ticker"]),
                _fmt_price(row["alert_price"], row["ticker"]),
            ]
            for row in group_rows
        ]
        table_str = render_table(headers, data_rows)
        if table_str:
            result.append({"label": label, "table_str": table_str, "details": _get_details(group_rows)})
    return result
