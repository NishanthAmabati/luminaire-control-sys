import asyncio
import logging
import os

from redis.asyncio import Redis
from services.timer_service import TimerService
from services.redis_listener import RedisListener

logging.basicConfig(level=logging.INFO)

def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        raise RuntimeError(f"missing required env var: {name}")
    return value

async def main():
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

    try:
        await timer.sync_from_redis()

        await asyncio.gather(
            timer.run(),
            listener.listen()
        )
    except (asyncio.CancelledError, KeyboardInterrupt):
        logging.info("shutdown requested")
    finally:
        logging.info("running cleanup...")
        await timer.shutdown()
        logging.info("shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())
