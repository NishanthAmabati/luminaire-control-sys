import asyncio
import logging
import os
from pythonjsonlogger import jsonlogger
from redis.asyncio import Redis

from services.timer_service import TimerService
from services.redis_listener import RedisListener

# 1. configure structured json logging for docker
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

async def main():
    log.info("initializing timer service architecture")
    
    try:
        redis_url = require_env("REDIS_URL")
        redis_instance = Redis.from_url(redis_url)

        timer = TimerService(
            redis_url=redis_instance, # passing the instance directly for efficiency
            pub_chan=require_env("TIMER_REDIS_PUB"),
            tz=require_env("TIMEZONE"),
            state_service_url=require_env("TIMER_STATE_SERVICE_URL")
        )

        listener = RedisListener(
            redis=redis_instance,
            sub_chan=require_env("STATE_REDIS_PUB"),
            timer=timer
        )

        # 2. initial state sync before starting loops
        log.info("syncing initial timer state from redis")
        await timer.sync_from_redis()

        log.info("timer service entering main execution loop")
        await asyncio.gather(
            timer.run(),
            listener.listen()
        )
        
    except (asyncio.CancelledError, KeyboardInterrupt):
        log.info("shutdown requested by system")
    except Exception:
        log.exception("unhandled exception in timer service main loop")
    finally:
        log.info("running cleanup and resource teardown")
        try:
            # shutdown timer and redis instance
            await timer.shutdown()
            await redis_instance.close()
        except NameError:
            pass
        log.info("timer service shutdown complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        # final fallback for absolute startup failures
        print(f"fatal timer service error {str(e).lower()}")