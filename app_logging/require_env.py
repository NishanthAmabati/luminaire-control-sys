import os
import structlog

log = structlog.get_logger()

def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        log.critical("missing_required_env_var", var=name)
        raise SystemExit(1)
    return value
