import asyncio
import os
import structlog

from redis.asyncio import Redis
from app_logging.logging_config import configure_logging
from services.scene_loader import SceneLoader
from services.scheduler_service import Scheduler
from services.redis_listener import RedisListener

configure_logging()
log = structlog.get_logger()

def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        raise RuntimeError(f"missing required env var: {name}")
    return value

async def main():
    log.info("scheduler_service_startup_initiated")
    
    try:
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
            interpolation_mode=require_env("SCHEDULER_INTERPOLATION_MODE"),
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

        log.info("syncing_initial_state")
        await scheduler.sync_from_redis()   # initial UI sync
        await scheduler.publish_available_scenes()

        log.info("scheduler_loops_starting")
        await asyncio.gather(
            scheduler.run(),
            listener.listen()
        )
        
    except Exception as e:
        log.critical("scheduler_service_startup_failed", error=str(e), exc_info=True)
    finally:
        log.info("scheduler_shutdown_sequence_started")
        if 'redis' in locals():
            try:
                await redis.aclose()
                await redis.connection_pool.disconnect()
            except Exception:
                log.error("redis_shutdown_failed", exc_info=True)
        log.info("scheduler_shutdown_complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass