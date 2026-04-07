import asyncio
import logging
import os
import traceback
from pythonjsonlogger import jsonlogger

from redis.asyncio import Redis
from services.scene_loader import SceneLoader
from services.scheduler_service import Scheduler
from services.redis_listener import RedisListener

# 1. create the handler and formatter
log_handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    '%(levelname)s %(name)s %(message)s %(asctime)s'
)
log_handler.setFormatter(formatter)

# 2. configure the root logger directly
# avoid basicConfig(force=True) here as it might reset your manual handler
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(log_handler)

# now use the logger as usual
log = logging.getLogger(__name__)

def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        log.error(f"missing required env var {name}")
        # we still raise here because the app cannot start without config
        # but the main loop will catch it and log it nicely
        raise ValueError(f"missing env var {name}")
    return value

async def main():
    try:
        log.info("starting light control system")
        
        redis_url = require_env("REDIS_URL")
        redis = Redis.from_url(redis_url)
        log.info(f"connected to redis at {redis_url}")

        cct_min = int(require_env("SCALES_CCT_MIN"))
        cct_max = int(require_env("SCALES_CCT_MAX"))
        lux_min = int(require_env("SCALES_LUX_MIN"))
        lux_max = int(require_env("SCALES_LUX_MAX"))

        scene_loader = SceneLoader(
            require_env("SCHEDULER_SCENES_DIR"),
            {
                "cct": {"min": cct_min, "max": cct_max},
                "lux": {"min": lux_min, "max": lux_max},
            }
        )
        
        scheduler = Scheduler(
            redis=redis,
            tz=require_env("TIMEZONE"),
            scene_loader=scene_loader,
            scheduler_interval=float(require_env("SCHEDULER_INTERVAL")),
            pub_chan=require_env("SCHEDULER_REDIS_PUB"),
            cct_min=cct_min,
            cct_max=cct_max,
            lux_min=lux_min,
            lux_max=lux_max,
            luminaire_service_url=require_env("SCHEDULER_LUMINAIRE_URL")
        )

        listener = RedisListener(
            redis=redis,
            sub_chan=require_env("STATE_REDIS_PUB"),
            scheduler=scheduler
        )

        log.info("performing initial sync and scene publishing")
        await scheduler.sync_from_redis()
        await scheduler.publish_available_scenes()

        log.info("entering main execution loop")
        await asyncio.gather(
            scheduler.run(),
            listener.listen()
        )

    except Exception as e:
        log.error(f"critical failure during startup {str(e).lower()}")
        log.debug(traceback.format_exc().lower())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("system shutdown requested by user")
    except Exception as e:
        # final fallback to ensure no unlogged crashes
        print(f"fatal error {str(e).lower()}")