import asyncio
import os
import uvicorn
import structlog

from redis.asyncio import Redis
from app_logging.logging_config import configure_logging
from app_logging.require_env import require_env
from services.state_service import StateService
from clients.redis_listener import RedisListener
from api.api_server import createAPI

configure_logging()
log = structlog.get_logger()

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
    log.info("fastapi_server_starting", host=fastAPIconfig.host, port=fastAPIconfig.port)
    await server.serve()

async def main():
    log.info("state_service_startup_initiated")
    require_env("REDIS_URL")
    require_env("STATE_API_HOST")
    require_env("STATE_API_PORT")
    require_env("STATE_API_LOOP")
    require_env("STATE_API_LOG_LEVEL")
    require_env("SCHEDULER_REDIS_PUB")
    require_env("METRICS_REDIS_PUB")
    
    try:
        redis_url = require_env("REDIS_URL")
        redis = Redis.from_url(redis_url)

        service = StateService(
            redis_url,
            state_key="system:state",
            channel="system:events"
        )

        listener = RedisListener(
            redis=redis,
            scheduler_sub_chan=require_env("SCHEDULER_REDIS_PUB"),
            metrics_sub_chan=require_env("METRICS_REDIS_PUB"),
            state_service=service
        )

        app = createAPI(service)

        log.info("state_service_components_initialized")
        await asyncio.gather(
            startFastAPI(app),
            listener.listen()
        )
    except Exception as e:
        log.critical("state_service_crashed", error=str(e), exc_info=True)
    finally:
        log.info("state_shutdown_sequence_started")
        if 'service' in locals():
            try:
                await service.shutdown()
            except Exception:
                log.error("state_service_shutdown_failed", exc_info=True)
                
        if 'redis' in locals():
             try:
                 await redis.aclose()
                 await redis.connection_pool.disconnect()
             except Exception:
                 log.error("redis_connection_close_failed", exc_info=True)
                 
        log.info("state_shutdown_complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass