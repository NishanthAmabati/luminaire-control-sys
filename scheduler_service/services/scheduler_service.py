import asyncio
import time
import json
import logging
import pytz

from datetime import datetime as dt
from datetime import timedelta
from services.scene_loader import SceneLoader
from services.interpolator import Interpolator
from services.light_channeler import LightChanneler
from clients.luminaire_client import LuminaireClient
from models.scheduler_runtime import SchedulerRuntime

log = logging.getLogger(__name__)

def minutes(t):
    return t.hour * 60 + t.minute

def interpolate(a, b, factor):
    return a + (b - a) * factor

class Scheduler:
    def __init__(
            self,
            redis,
            tz,
            scene_loader,
            scheduler_interval,
            pub_chan,
            cct_min, cct_max,
            lux_min, lux_max,
            luminaire_service_url,
        ):
        self.redis = redis
        self.tz = pytz.timezone(tz)
        self.scene_loader = scene_loader
        self.scenes = self.scene_loader.load_all()
        self.runtime = SchedulerRuntime()
        self.running = True
        self.runtime.available_scenes = list(self.scenes.keys())
        self.scheduler_interval = scheduler_interval
        self.pub_chan = pub_chan
        self.interpolator = Interpolator(self.runtime, self.scenes, self.tz)
        self.channeler = LightChanneler(
                    cct_min=cct_min, cct_max=cct_max, 
                    lux_min=lux_min, lux_max=lux_max
                )
        self.luminaire_service_url = luminaire_service_url
        self.luminaire_client = LuminaireClient(self.luminaire_service_url)

    async def publish_state(self):
        try:
            payload = {
                "system_on": self.runtime.system_on,
                "mode": self.runtime.mode,
                "available_scenes": self.runtime.available_scenes,
                "loaded_scene": self.runtime.loaded_scene,
                "running_scene": self.runtime.running_scene,
                #"progress": self.runtime.progress,
                #"cct": self.runtime.cct,
                #"lux": self.runtime.lux,
            }
            await self.redis.publish(
                self.pub_chan,
                json.dumps({
                    "event": "scheduler:state",
                    "payload": payload,
                    "ts": str(dt.now(self.tz))
                })
            )
        except Exception as e:
            log.info(f"failed to publish scheduler state to redis, chan: '{self.pub_chan}', err: {e}")

    async def publish_runtime(self):
        payload = {
            #"mode": self.runtime.mode,
            "cct": self.runtime.cct,
            "lux": self.runtime.lux,
            "cw": self.runtime.cw,
            "ww": self.runtime.ww,
            "progress": self.runtime.progress
        }
        await self.redis.publish(
            self.pub_chan,
            json.dumps({
                "event": "scheduler:runtime",
                "payload": payload,
                "ts": str(dt.now(self.tz))
            })
        )
        log.debug(f"scheduler runtime published to redis, chan: '{self.pub_chan}', event: 'scheduler:runtime'")

    async def tick(self):
        if not self.runtime.system_on:
            target_cct, target_lux = 0.0, 0.0
            self.runtime.cct, self.runtime.lux = 0.0, 0.0
        
        elif self.runtime.mode == "MANUAL":
            target_cct = self.runtime.cct
            target_lux = self.runtime.lux

        elif self.runtime.mode == "AUTO" and self.runtime.running_scene:
            await self.interpolator.compute_current_values()
            target_cct = self.runtime.cct
            target_lux = self.runtime.lux
        else:
            target_cct, target_lux = self.runtime.cct, self.runtime.lux

        result = self.channeler.resolve_channels(target_cct, target_lux)
        
        if result:
            self.runtime.cw, self.runtime.ww = result["cw"], result["ww"]
            await self.luminaire_client.send(self.runtime.cw, self.runtime.ww)
            log.debug("tick_executed", extra={
                "system_on": self.runtime.system_on,
                "cw": self.runtime.cw, 
                "ww": self.runtime.ww
            })
            await self.publish_runtime()

    async def run(self):
        log.info("started scheduler loop")
        while self.running:
            await self.tick()
            await asyncio.sleep(self.scheduler_interval)

    async def publish_available_scenes(self):
        payload = {
            "scenes": list(self.scenes.keys())
        }
        await self.redis.publish(
            self.pub_chan,
            json.dumps({
                "event": "scheduler:available_scenes",
                "payload": payload,
                "ts": str(dt.now(self.tz))
            })
        )
        log.info(f"publised scenes to redis, chan: '{self.pub_chan}', event: 'scheduler:available_scenes'")

    async def sync_from_redis(self):
        await self.handle_mode()

    async def handle_power(self):
        raw = await self.redis.get("system:state")
        if not raw:
            return

        state = json.loads(raw)

        self.runtime.system_on = state.get("system_on", False)
        if self.runtime.system_on == True:
            await self.handle_mode()
        else:
            await self.deactivate_scene()
            self.runtime.cct = 0
            self.runtime.lux = 0
            await self.publish_state()
            await self.publish_runtime()

    async def handle_mode(self):
        raw = await self.redis.get("system:state")
        if not raw:
            return

        state = json.loads(raw)

        self.runtime.system_on = state.get("system_on", False)
        self.runtime.mode = state.get("mode", "MANUAL")

        manual = state.get("manual", {})
        auto = state.get("auto", {})

        if self.runtime.mode == "MANUAL":
            await self.deactivate_scene()
            
            manual_lux = manual.get("lux", 0)
            self.runtime.lux = manual_lux
            manual_cw = manual.get("cw")
            manual_ww = manual.get("ww")
            last_toggle = manual.get("last_toggle")
            
            if last_toggle == "buttons":
                if manual_cw is not None and manual_ww is not None:
                    await self.apply_manual(
                        "buttons",
                        cw=manual_cw,
                        ww=manual_ww,
                    )
                else:
                    log.exception(f"unable to switch mode with values: cw: {manual_cw}, ww: {manual_ww}")
            elif last_toggle == "sliders":
                await self.apply_manual(
                    "sliders",
                    cct=manual.get("cct", 0),
                    lux=manual_lux,
                )

        elif self.runtime.mode == "AUTO":
            self.runtime.loaded_scene = auto.get("loaded_scene")
            self.runtime.running_scene = auto.get("running_scene")

            if self.runtime.loaded_scene:
                await self.load_scene(self.runtime.loaded_scene)
            
            if self.runtime.running_scene:
                await self.interpolator.compute_current_values()
                res = self.channeler.resolve_channels(self.runtime.cct, self.runtime.lux)
                self.runtime.cw, self.runtime.ww = res["cw"], res["ww"]

        await self.publish_state()
        await self.publish_runtime()  

    async def load_scene(self, scene_name: str):
        if scene_name not in self.scenes:
            log.exception(f"scene not found: {scene_name}")
            return
        self.runtime.loaded_scene = scene_name
        scene = self.scenes.get(scene_name)
        # Convert time objects to strings so JSON can handle them
        serializable_points = [
            {**point, "time": point["time"].strftime("%H:%M")} 
            for point in scene
        ]
        await self.redis.publish(
            self.pub_chan,
            json.dumps({
                "event": "scheduler:scene_load",
                "payload": {
                    "loaded_scene": scene_name,
                    "points": serializable_points  # full CSV parsed structure
                },
                "ts": str(dt.now(self.tz))
            })
        )

    async def activate_scene(self, scene_name: str):
        if scene_name not in self.scenes:
            log.exception(f"scene not found: {scene_name}")
            return
        
        if self.runtime.mode != "AUTO":
            log.info("ignoring scene activation while not in AUTO")
            return
        await self.deactivate_scene()
        await self.load_scene(scene_name)
        self.runtime.running_scene = scene_name
        self.runtime.progress = 0.0
        
        await self.interpolator.compute_current_values()

        await self.publish_state()
        await self.publish_runtime()

    async def deactivate_scene(self):

        if not self.runtime.running_scene:
            return
        self.runtime.loaded_scene = None
        self.runtime.running_scene = None
        self.runtime.progress = 0.0

        # Optional: keep last cct/lux or reset?
        # I recommend KEEPING last values.
        # Do NOT force 0.

        #await self.publish_runtime()
        await self.publish_state()

    # async def apply_manual(self, cct: float, lux: float):
    async def apply_manual(self,
                            medium: str,
                            cct: float | None = None,
                            lux: float | None = None,
                            cw: int | None = None,
                            ww: int | None = None
                            ):
        if medium == "sliders":
            if cct is None or lux is None:
                return
            self.runtime.cct = cct
            self.runtime.lux = lux
            self.runtime.progress = 0.0
            result = self.channeler.resolve_channels(self.runtime.cct, self.runtime.lux)
            if not result:
                return
            self.runtime.cw = result["cw"]
            self.runtime.ww = result["ww"]
        elif medium == "buttons":
            if cw is None or ww is None:
                return
            result = self.channeler.resolve_cct(cw, ww)
            if not result:
                return
            self.runtime.cct = result["cct"]
            self.runtime.progress = 0.0
            # keep existing lux
            result = self.channeler.resolve_channels(self.runtime.cct, self.runtime.lux)
            if not result:
                return
            self.runtime.cw = result["cw"]
            self.runtime.ww = result["ww"]
