from contextvars import ContextVar
from typing import Optional

_current_trace_id: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)


def set_trace_id(trace_id: str) -> None:
    _current_trace_id.set(trace_id)


def get_trace_id() -> Optional[str]:
    return _current_trace_id.get()


def clear_trace_id() -> None:
    _current_trace_id.set(None)
