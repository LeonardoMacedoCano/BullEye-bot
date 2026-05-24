import uuid
from contextvars import ContextVar

_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    return _request_id.get()


def new_request_id() -> str:
    """Generate a short request ID, bind it to the current context, and return it."""
    rid = uuid.uuid4().hex[:8]
    _request_id.set(rid)
    return rid
