import asyncio
import logging
import os

from services.metrics_service import MetricsService

logging.basicConfig(level=logging.INFO)

def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        raise RuntimeError(f"missing required env var: {name}")
    return value

async def main():
    service = MetricsService(
        redis_url=require_env("REDIS_URL"),
        channel=require_env("METRICS_REDIS_PUB"),
        interval_s=float(require_env("METRICS_INTERVAL")),
    )

    try:
        await service.run()
    except (asyncio.CancelledError, KeyboardInterrupt):
        logging.info("shutdown requested")
    finally:
        logging.info("running cleanup...")
        await service.shutdown()
        logging.info("shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())
