import uvicorn
import logging
import asyncio
import os

from redis.asyncio import Redis
from services.state_service import StateService
from clients.redis_listener import RedisListener
from api.api_server import createAPI

logging.basicConfig(level=logging.INFO)

def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        raise RuntimeError(f"missing required env var: {name}")
    return value

def parse_bool(value: str) -> bool:
    return value.lower() in ("1", "true", "yes", "on")

async def startFastAPI(app):
    fastAPIconfig = uvicorn.Config(
        app,
        host=require_env("STATE_API_HOST"),
        port=int(require_env("STATE_API_PORT")),
        loop=require_env("STATE_API_LOOP"),
        log_level=require_env("STATE_API_LOG_LEVEL"),
        access_log=parse_bool(os.getenv("STATE_API_ACCESS_LOG", "false")),
    )
    server = uvicorn.Server(fastAPIconfig)
    await server.serve()

async def main():
    redis = Redis.from_url(require_env("REDIS_URL"))

    service = StateService(
        require_env("REDIS_URL"),
        state_key="system:state",
        channel="system:events"
    )

    lisnter = RedisListener(
        redis=redis,
        scheduler_sub_chan=require_env("SCHEDULER_REDIS_PUB"),
        metrics_sub_chan=require_env("METRICS_REDIS_PUB"),
        state_service=service
    )

    app = createAPI(service)

    try:
        await asyncio.gather(
            startFastAPI(app),
            lisnter.listen()
        )
    except (asyncio.CancelledError, KeyboardInterrupt):
        logging.info("shutdown requested")
    finally:
        logging.info("running cleanup...")
        await service.shutdown()
        logging.info("shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())
