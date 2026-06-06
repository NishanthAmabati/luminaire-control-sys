import os
import structlog
import pytz
from datetime import datetime

TZ_ENV = os.getenv("TIMEZONE", "UTC")
tz_fallback_triggered = False

try:
    LOCAL_TZ = pytz.timezone(TZ_ENV)
except pytz.UnknownTimeZoneError:
    LOCAL_TZ = pytz.UTC
    tz_fallback_triggered = True

def local_timestamper(logger, log_method, event_dict):
    event_dict["timestamp"] = datetime.now(LOCAL_TZ).isoformat()
    return event_dict

def configure_logging():
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        local_timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.CallsiteParameterAdder({
            structlog.processors.CallsiteParameter.FILENAME,
            structlog.processors.CallsiteParameter.FUNC_NAME,
            structlog.processors.CallsiteParameter.LINENO,
        }),
    ]


    processor = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors + [processor],
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    init_log = structlog.get_logger()
    if tz_fallback_triggered:
        init_log.warning(
            "invalid_timezone_fallback", 
            provided_tz=TZ_ENV, 
            fallback_tz="UTC", 
            reason="pytz.UnknownTimeZoneError"
        )
    else:
        init_log.info("logging_timezone_configured", tz=LOCAL_TZ.zone)

log = structlog.get_logger()