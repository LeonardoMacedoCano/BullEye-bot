import logging
import time
from typing import Callable, TypeVar

import requests

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_BACKOFF = 2.0  # delay = BACKOFF ** (attempt - 1): 1s, 2s

T = TypeVar("T")


def fetch_with_retry(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: int = 10,
    max_attempts: int = _MAX_ATTEMPTS,
    backoff: float = _BACKOFF,
) -> requests.Response:
    """GET with exponential backoff. Raises the last exception if all attempts fail."""
    last_exc: Exception
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp
        except Exception as exc:
            last_exc = exc
            if attempt < max_attempts:
                delay = backoff ** (attempt - 1)
                logger.warning(
                    "Request to %s failed (attempt %d/%d): %s — retrying in %.1fs",
                    url, attempt, max_attempts, exc, delay,
                )
                time.sleep(delay)
    raise last_exc


def call_with_retry(
    fn: Callable[..., T],
    *args,
    max_attempts: int = _MAX_ATTEMPTS,
    backoff: float = _BACKOFF,
    **kwargs,
) -> T:
    """Call fn(*args, **kwargs) with exponential backoff. Raises the last exception if all attempts fail."""
    last_exc: Exception
    for attempt in range(1, max_attempts + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt < max_attempts:
                delay = backoff ** (attempt - 1)
                logger.warning(
                    "Call to %s failed (attempt %d/%d): %s — retrying in %.1fs",
                    getattr(fn, "__name__", repr(fn)), attempt, max_attempts, exc, delay,
                )
                time.sleep(delay)
    raise last_exc
