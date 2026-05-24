from __future__ import annotations

MSG_LIMIT = 1900


def display_name(ticker: str) -> str:
    if ticker.upper() == "BTC-USD":
        return "BTC"
    return ticker[:-3] if ticker.upper().endswith(".SA") else ticker


def currency(ticker: str) -> str:
    return "R$" if ticker.upper().endswith(".SA") else "$"


def fmt(value: float, symbol: str) -> str:
    return f"{symbol}{value:,.2f}"


def fmt_pct(pct: float) -> str:
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"


def render_table(
    headers: list[str],
    rows: list[list[str]],
    required_headers: list[str] | None = None,
) -> str:
    required = set(required_headers or [])
    active = [
        i for i in range(len(headers))
        if headers[i] in required or any(r[i] != "—" for r in rows)
    ]
    if not active:
        return ""
    widths = [
        max(len(headers[i]), max((len(r[i]) for r in rows), default=0)) + 1
        for i in active
    ]
    header_line = "".join(f"{headers[i]:<{w}}" for i, w in zip(active, widths))
    sep = "─" * sum(widths)
    data_lines = [
        "".join(f"{r[i]:<{w}}" for i, w in zip(active, widths))
        for r in rows
    ]
    return "\n".join([header_line, sep] + data_lines)


def pack_messages(sections: list[str]) -> list[str]:
    packed: list[str] = []
    current = ""
    for s in sections:
        if not current:
            current = s
        elif len(current) + 1 + len(s) <= MSG_LIMIT:
            current += "\n" + s
        else:
            packed.append(current)
            current = s
    if current:
        packed.append(current)
    return packed


def group_by_subcategory(
    rows: list, subcategory_order: list[str]
) -> list[tuple[str | None, list]]:
    groups: dict[str | None, list] = {}
    for row in rows:
        try:
            key = row["subcategory"]
        except (IndexError, KeyError):
            key = None
        if key not in groups:
            groups[key] = []
        groups[key].append(row)

    ordered = []
    for key in subcategory_order:
        if key in groups:
            ordered.append((key, groups[key]))
    for key, vals in groups.items():
        if key is not None and key not in subcategory_order:
            ordered.append((key, vals))
    if None in groups:
        ordered.append((None, groups[None]))
    return ordered
