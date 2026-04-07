import asyncio
import logging
import os
from pythonjsonlogger import jsonlogger

from services.metrics_service import MetricsService

# 1. configure structured json logging for loki/dozzle
log_handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    '%(levelname)s %(name)s %(message)s %(asctime)s'
)
log_handler.setFormatter(formatter)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(log_handler)

log = logging.getLogger("main")

def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        log.error(f"missing required env var {name}")
        raise RuntimeError(f"missing required env var {name}")
    return value

def parse_float_env(name: str, default: float = 5.0) -> float:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        log.error(f"invalid float value for {name}")
        raise RuntimeError(f"invalid float value for {name}")

async def main():
    log.info("initializing metrics service architecture")
    
    try:
        service = MetricsService(
            redis_url=require_env("REDIS_URL"),
            channel=require_env("METRICS_REDIS_PUB"),
            interval_s=parse_float_env("METRICS_INTERVAL", 5.0),
        )

        log.info("entering main metrics collection loop")
        await service.run()
        
    except (asyncio.CancelledError, KeyboardInterrupt):
        log.info("shutdown requested by system")
    except Exception:
        log.exception("unhandled exception in metrics service main loop")
    finally:
        log.info("running cleanup and resource teardown")
        try:
            await service.shutdown()
        except NameError:
            pass
        log.info("metrics service shutdown complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        # final fallback for absolute startup failures
        print(f"fatal metrics service error {str(e).lower()}")