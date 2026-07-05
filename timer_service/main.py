import asyncio
import os
import structlog

from redis.asyncio import Redis
from app_logging.logging_config import configure_logging
from app_logging.require_env import require_env
from services.timer_service import TimerService
from services.redis_listener import RedisListener

configure_logging()
log = structlog.get_logger()

async def main():
    log.info("timer_service_startup_initiated")
    require_env("REDIS_URL")
    require_env("TIMER_REDIS_PUB")
    require_env("TIMEZONE")
    require_env("TIMER_STATE_SERVICE_URL")
    require_env("STATE_REDIS_PUB")
    
    try:
        redis = Redis.from_url(require_env("REDIS_URL"))

        timer = TimerService(
            redis_url=redis,
            pub_chan=require_env("TIMER_REDIS_PUB"),
            tz=require_env("TIMEZONE"),
            state_service_url=require_env("TIMER_STATE_SERVICE_URL")
        )

        listener = RedisListener(
            redis=redis,
            sub_chan=require_env("STATE_REDIS_PUB"),
            timer=timer
        )

        log.info("syncing_initial_timer_state")
        await timer.sync_from_redis()

        log.info("timer_service_loops_starting")
        await asyncio.gather(
            timer.run(),
            listener.listen()
        )
        
    except asyncio.CancelledError:
        log.info("timer_service_task_cancelled")
    except Exception as e:
        log.critical("timer_service_crashed", error=str(e), exc_info=True)
    finally:
        log.info("timer_shutdown_sequence_started")
        if 'timer' in locals():
            try:
                await timer.shutdown()
            except Exception:
                log.error("timer_service_shutdown_failed", exc_info=True)        
        log.info("timer_shutdown_complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass