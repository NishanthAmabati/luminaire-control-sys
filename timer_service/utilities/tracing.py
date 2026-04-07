import uuid
import logging
from typing import Optional, Any, Dict

TRACE_ID_KEY = "trace_id"


class TraceLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        extra = kwargs.get("extra", {})
        extra["trace_id"] = self.extra.get(TRACE_ID_KEY)
        kwargs["extra"] = extra
        return msg, kwargs


def create_trace_logger(
    logger: logging.Logger, trace_id: Optional[str] = None
) -> TraceLoggerAdapter:
    return TraceLoggerAdapter(logger, {TRACE_ID_KEY: trace_id or str(uuid.uuid4())})


def extract_trace_id(data: Dict[str, Any]) -> Optional[str]:
    return data.get(TRACE_ID_KEY)


def generate_trace_id() -> str:
    return str(uuid.uuid4())


def is_valid_uuid(trace_id: str) -> bool:
    try:
        uuid.UUID(trace_id)
        return True
    except (ValueError, TypeError):
        return False
