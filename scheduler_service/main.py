import asyncio
import logging
import os

from redis.asyncio import Redis
from services.scene_loader import SceneLoader
from services.scheduler_service import Scheduler
from services.redis_listener import RedisListener

logging.basicConfig(level=logging.INFO)

def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        raise RuntimeError(f"missing required env var: {name}")
    return value

async def main():
    redis = Redis.from_url(require_env("REDIS_URL"))

    scene_loader = SceneLoader(
        require_env("SCHEDULER_SCENES_DIR"),
        {
            "cct": {
                "min": int(require_env("SCALES_CCT_MIN")),
                "max": int(require_env("SCALES_CCT_MAX")),
            },
            "lux": {
                "min": int(require_env("SCALES_LUX_MIN")),
                "max": int(require_env("SCALES_LUX_MAX")),
            },
        }
    )
    scheduler = Scheduler(
        redis=redis,
        tz=require_env("TIMEZONE"),
        scene_loader=scene_loader,
        scheduler_interval=float(require_env("SCHEDULER_INTERVAL")),
        pub_chan=require_env("SCHEDULER_REDIS_PUB"),
        cct_min=int(require_env("SCALES_CCT_MIN")),
        cct_max=int(require_env("SCALES_CCT_MAX")),
        lux_min=int(require_env("SCALES_LUX_MIN")),
        lux_max=int(require_env("SCALES_LUX_MAX")),
        luminaire_service_url=require_env("SCHEDULER_LUMINAIRE_URL")
    )
    listener = RedisListener(
        redis=redis,
        sub_chan=require_env("STATE_REDIS_PUB"),
        scheduler=scheduler
    )

    await scheduler.sync_from_redis()   # initial UI sync
    await scheduler.publish_available_scenes()

    await asyncio.gather(
        scheduler.run(),
        listener.listen()
    )

if __name__ == "__main__":
    asyncio.run(main())
