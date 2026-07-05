import asyncio
import os
import structlog

from app_logging.logging_config import configure_logging
from app_logging.require_env import require_env
from services.metrics_service import MetricsService

configure_logging()
log = structlog.get_logger()

async def main():
    log.info("metrics_service_startup_initiated")
    require_env("REDIS_URL")
    require_env("METRICS_REDIS_PUB")
    require_env("METRICS_INTERVAL")
    
    try:
        service = MetricsService(
            redis_url=require_env("REDIS_URL"),
            channel=require_env("METRICS_REDIS_PUB"),
            interval_s=float(require_env("METRICS_INTERVAL")),
        )

        log.info("metrics_loop_starting", interval_s=float(require_env("METRICS_INTERVAL")))
        await service.run()
        
    except asyncio.CancelledError:
        log.info("metrics_service_task_cancelled")
    except Exception as e:
        log.critical("metrics_service_crashed", error=str(e), exc_info=True)
    finally:
        log.info("metrics_shutdown_sequence_started")
        if 'service' in locals():
            try:
                await service.shutdown()
            except Exception:
                log.error("metrics_service_shutdown_failed", exc_info=True)
        log.info("metrics_shutdown_complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass