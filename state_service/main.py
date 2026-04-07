import asyncio
import logging
import os
import uvicorn
from pythonjsonlogger import jsonlogger
from redis.asyncio import Redis

from services.state_service import StateService
from clients.redis_listener import RedisListener
from api.api_server import createAPI

# 1. configure structured json logging
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

def parse_bool(value: str) -> bool:
    if not value:
        return False
    return value.lower() in ("1", "true", "yes", "on")

async def start_fastapi(app):
    try:
        config = uvicorn.Config(
            app,
            host=require_env("STATE_API_HOST"),
            port=int(require_env("STATE_API_PORT")),
            loop=require_env("STATE_API_LOOP"),
            log_level=require_env("STATE_API_LOG_LEVEL").lower(),
            access_log=parse_bool(os.getenv("STATE_API_ACCESS_LOG", "false")),
        )
        server = uvicorn.Server(config)
        log.info("starting state api server")
        await server.serve()
    except Exception:
        log.exception("critical failure in state api server")
        raise

async def main():
    log.info("initializing state service architecture")
    
    try:
        redis_url = require_env("REDIS_URL")
        redis_instance = Redis.from_url(redis_url)

        service = StateService(
            redisURL=redis_url,
            state_key="system:state",
            channel="system:events"
        )
        
        # load persisted state from redis before starting listener
        await service.load()

        listener = RedisListener(
            redis=redis_instance,
            scheduler_sub_chan=require_env("SCHEDULER_REDIS_PUB"),
            metrics_sub_chan=require_env("METRICS_REDIS_PUB"),
            state_service=service
        )

        app = createAPI(service)

        log.info("state service entering main execution loop")
        await asyncio.gather(
            start_fastapi(app),
            listener.listen()
        )
        
    except (asyncio.CancelledError, KeyboardInterrupt):
        log.info("shutdown requested by system")
    except Exception:
        log.exception("unhandled exception in state service main loop")
    finally:
        log.info("running cleanup and resource teardown")
        try:
            await service.shutdown()
            await redis_instance.close()
        except NameError:
            pass
        log.info("state service shutdown complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        # final fallback for startup-blocking errors
        print(f"fatal state service error {str(e).lower()}")