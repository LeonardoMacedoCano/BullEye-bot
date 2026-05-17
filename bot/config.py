import logging
import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

load_dotenv()

TIMEZONE_NAME: str = os.getenv("TIMEZONE") or "UTC"
try:
    TIMEZONE = ZoneInfo(TIMEZONE_NAME)
except ZoneInfoNotFoundError:
    logging.getLogger(__name__).warning("Unknown TIMEZONE %r, falling back to UTC", TIMEZONE_NAME)
    TIMEZONE_NAME = "UTC"
    TIMEZONE = ZoneInfo("UTC")

PRICE_CACHE_TTL:      int = int(os.getenv("PRICE_CACHE_TTL_MINUTES")      or 5)  * 60
DIV_CACHE_TTL:        int = int(os.getenv("DIV_CACHE_TTL_HOURS")           or 24) * 3600
FEAR_GREED_CACHE_TTL: int = int(os.getenv("FEAR_GREED_CACHE_TTL_MINUTES") or 30) * 60
