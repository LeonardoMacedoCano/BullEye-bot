from __future__ import annotations

import datetime
import discord

from bot.shared.formatting import ansi_pct, strip_ansi
from bot.shared.embeds import EMBED_COLOR, COLOR_UP, COLOR_DOWN, wrap_table_field
from bot.shared.dividends_embed import dividends_field_value


def build_portfolio_embed(data: dict) -> discord.Embed | None:
    wallet_groups = data.get("wallet_groups", [])
    watchlist_groups = data.get("watchlist_groups", [])
    if not wallet_groups and not watchlist_groups:
        return None

    avg_change = data.get("avg_day_change")
    if avg_change is not None:
        if avg_change > 0.5:
            color = COLOR_UP
        elif avg_change < -0.5:
            color = COLOR_DOWN
        else:
            color = EMBED_COLOR
    else:
        color = EMBED_COLOR

    now = datetime.datetime.now(datetime.timezone.utc)
    embed = discord.Embed(title="📊 Portfolio", color=color, timestamp=now)
    embed.set_footer(text="Prices via yfinance · /refreshcache to force refresh")

    for group in wallet_groups:
        label = "💼 Wallet" + (f" · {group['label']}" if group["label"] else "")
        embed.add_field(name=label, value=wrap_table_field(group["table_str"]), inline=False)

    for group in watchlist_groups:
        label = "👀 Watchlist" + (f" · {group['label']}" if group["label"] else "")
        embed.add_field(name=label, value=wrap_table_field(group["table_str"]), inline=False)

    return embed


def _market_field_value(market: dict) -> str:
    rows: list[tuple[str, str, str, str]] = []
    if market["vix"]:
        v = market["vix"]
        rows.append(("VIX", f"{v['level']:.1f}", ansi_pct(v["day_change_pct"]), v["status"]))
    if market["ibov"]:
        ib = market["ibov"]
        rows.append(("IBOV", f"{ib['level']:,.0f}", ansi_pct(ib["day_change_pct"]), ""))
    if market["fgi"]:
        fg = market["fgi"]
        rows.append(("F&G", str(fg["value"]), "—", fg["classification"]))
    if not rows:
        return "```ansi\n—\n```"
    n_w = max(len(r[0]) for r in rows)
    v_w = max(len(r[1]) for r in rows)
    p_w = max(len(strip_ansi(r[2])) for r in rows)
    lines = []
    for name, val, pct, status in rows:
        vis_pad = p_w - len(strip_ansi(pct))
        line = f"{name:<{n_w}}  {val:>{v_w}}  {pct}{' ' * vis_pad}"
        if status:
            line += f"  {status}"
        lines.append(line.rstrip())
    result = "```ansi\n" + "\n".join(lines) + "\n```"
    if market["fgi"] and market["fgi"].get("fgi_ceiling") is not None:
        fg = market["fgi"]
        delta = fg["fgi_ceiling"] - fg["value"]
        if delta >= 0:
            note = f"F&G ceiling {fg['fgi_ceiling']} · buy signal active (+{delta})"
        else:
            note = f"F&G ceiling {fg['fgi_ceiling']} · {abs(delta)}pt to trigger"
        result += f"\n*{note}*"
    return result


def _performance_field_value(performance: dict) -> str | None:
    lines: list[str] = []
    groups = performance["groups"]
    for group in groups:
        if len(groups) > 1:
            lines.append(group["label"])
        for p in group["periods"]:
            best = p["best"]
            worst = p["worst"]
            plabel = f"{p['label']:<5}"
            if p["same"]:
                arrow = "▲" if best["value"] >= 0 else "▼"
                lines.append(f"  {plabel} {arrow}{best['name']} {ansi_pct(best['value'])}")
            else:
                parts: list[str] = []
                if best["value"] > 0:
                    parts.append(f"▲{best['name']} {ansi_pct(best['value'])}")
                if worst["value"] < 0:
                    parts.append(f"▼{worst['name']} {ansi_pct(worst['value'])}")
                if parts:
                    lines.append(f"  {plabel} " + "  ".join(parts))
    return ("```ansi\n" + "\n".join(lines) + "\n```") if lines else None


def _opportunities_field_value(opportunities: dict) -> str | None:
    ticker_opps = opportunities.get("ticker_opps", [])
    fgi_triggered = opportunities.get("fgi_triggered", False)
    fgi_data = opportunities.get("fgi_data")
    all_names = [opp["name"] for opp in ticker_opps]
    if fgi_triggered and fgi_data:
        all_names.append("BTC")
    name_w = max((len(n) for n in all_names), default=6)
    indent = " " * (name_w + 2)
    lines: list[str] = []
    for opp in ticker_opps:
        lines.append(f"{opp['name']:<{name_w}}  {opp['price']} → {opp['ceiling']}")
        margin_colored = f"\x1b[1;32m{opp['margin']} upside\x1b[0m"
        lines.append(f"{indent}{margin_colored}  [{opp['category']}]")
    if fgi_triggered and fgi_data:
        delta = fgi_data["ceiling"] - fgi_data["value"]
        lines.append(f"{'BTC':<{name_w}}  F&G {fgi_data['value']} ≤ ceil {fgi_data['ceiling']} (+{delta})")
        lines.append(f"{indent}{fgi_data['classification']}")
    return ("```ansi\n" + "\n".join(lines) + "\n```") if lines else None


def build_intelligence_embed(
    data: dict,
) -> discord.Embed | None:
    market = data.get("market")
    performance = data.get("performance")
    dividends = data.get("dividends", [])
    opportunities = data.get("opportunities", {})

    has_opps = bool(opportunities.get("ticker_opps")) or bool(opportunities.get("fgi_triggered"))
    has_content = market or performance or dividends or has_opps

    if not has_content:
        return None

    now = datetime.datetime.now(datetime.timezone.utc)
    embed = discord.Embed(title="📈 Market Intelligence", color=EMBED_COLOR, timestamp=now)
    embed.set_footer(text="VIX & IBOV via yfinance · Fear & Greed via alternative.me")

    if market:
        embed.add_field(name="📊 Indicators", value=_market_field_value(market), inline=False)

    if performance:
        perf_val = _performance_field_value(performance)
        if perf_val:
            embed.add_field(name="🏆 Best & Worst", value=perf_val, inline=False)

    if dividends:
        embed.add_field(
            name="📅 Upcoming Dividends",
            value=dividends_field_value(dividends),
            inline=False,
        )

    if has_opps:
        opp_val = _opportunities_field_value(opportunities)
        if opp_val:
            embed.add_field(name="🛒 Buy Opportunities", value=opp_val, inline=False)

    if not embed.fields:
        return None

    return embed
