import logging
from bot.services.market import get_ticker_data

logger = logging.getLogger(__name__)


def get_vix() -> dict | None:
    data = get_ticker_data("^VIX")
    if not data:
        return None
    level = data["current_price"]
    if level < 15:
        status = "Calm"
    elif level < 25:
        status = "Moderate"
    elif level < 30:
        status = "High Fear"
    else:
        status = "Extreme Fear"
    return {
        "level": level,
        "day_change_pct": data.get("day_change_pct", 0.0),
        "status": status,
    }


def get_ibov() -> dict | None:
    data = get_ticker_data("^BVSP")
    if not data:
        return None
    return {
        "level": data["current_price"],
        "day_change_pct": data.get("day_change_pct", 0.0),
    }
