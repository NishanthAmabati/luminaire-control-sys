import asyncio
import time
import json
import logging
import pytz
import traceback

from datetime import datetime as dt
from datetime import timedelta
from services.scene_loader import SceneLoader
from services.interpolator import Interpolator
from services.light_channeler import LightChanneler
from clients.luminaire_client import LuminaireClient
from models.scheduler_runtime import SchedulerRuntime
from utilities.tracing import create_trace_logger
from utilities.trace_context import get_trace_id

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
        cct_min,
        cct_max,
        lux_min,
        lux_max,
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
            cct_min=cct_min, cct_max=cct_max, lux_min=lux_min, lux_max=lux_max
        )
        self.luminaire_service_url = luminaire_service_url
        self.luminaire_client = LuminaireClient(self.luminaire_service_url)
        log.info("scheduler instance initialized")

    async def publish_state(self, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        try:
            payload = {
                "system_on": self.runtime.system_on,
                "mode": self.runtime.mode,
                "available_scenes": self.runtime.available_scenes,
                "loaded_scene": self.runtime.loaded_scene,
                "running_scene": self.runtime.running_scene,
            }
            await self.redis.publish(
                self.pub_chan,
                json.dumps(
                    {
                        "event": "scheduler:state",
                        "payload": payload,
                        "trace_id": trace_id,
                        "ts": str(dt.now(self.tz)),
                    }
                ),
            )
            trace_log.debug("published scheduler state to redis")
        except Exception as e:
            trace_log.error(
                "failed to publish scheduler state to redis chan %s error %s",
                self.pub_chan,
                str(e).lower(),
            )
            trace_log.debug(traceback.format_exc().lower())

    async def publish_runtime(self, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        try:
            payload = {
                "cct": self.runtime.cct,
                "lux": self.runtime.lux,
                "progress": self.runtime.progress,
            }
            await self.redis.publish(
                self.pub_chan,
                json.dumps(
                    {
                        "event": "scheduler:runtime",
                        "payload": payload,
                        "trace_id": trace_id,
                        "ts": str(dt.now(self.tz)),
                    }
                ),
            )
            trace_log.debug(
                "scheduler runtime published to redis chan %s", self.pub_chan
            )
        except Exception as e:
            trace_log.error(
                "failed to publish runtime to redis error %s", str(e).lower()
            )
            trace_log.debug(traceback.format_exc().lower())

    async def tick(self, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        try:
            if not self.runtime.system_on:
                target_cct, target_lux = 0.0, 0.0
                self.runtime.cct, self.runtime.lux = 0.0, 0.0
                trace_log.debug("tick system is off using zero values")

            elif self.runtime.mode == "MANUAL":
                target_cct = self.runtime.cct
                target_lux = self.runtime.lux
                trace_log.debug(
                    "tick manual mode using cct %s and lux %s", target_cct, target_lux
                )

            elif self.runtime.mode == "AUTO" and self.runtime.running_scene:
                await self.interpolator.compute_current_values()
                target_cct = self.runtime.cct
                target_lux = self.runtime.lux
                trace_log.debug(
                    "tick auto mode interpolated to cct %s and lux %s",
                    target_cct,
                    target_lux,
                )
            else:
                target_cct, target_lux = self.runtime.cct, self.runtime.lux
                trace_log.debug(
                    "tick default using existing cct %s and lux %s",
                    target_cct,
                    target_lux,
                )

            result = self.channeler.resolve_channels(target_cct, target_lux)

            if result:
                self.runtime.cw, self.runtime.ww = result["cw"], result["ww"]
                trace_log.debug(
                    "sending to luminaire client values cw %s ww %s",
                    self.runtime.cw,
                    self.runtime.ww,
                )
                await self.luminaire_client.send(self.runtime.cw, self.runtime.ww)
                await self.publish_runtime(trace_id)
            else:
                trace_log.warning("tick resolve_channels returned no result")
        except Exception as e:
            trace_log.error("error during scheduler tick %s", str(e).lower())
            trace_log.debug(traceback.format_exc().lower())

    async def run(self):
        log.info("started scheduler loop")
        while self.running:
            try:
                await self.tick()
            except Exception as e:
                trace_id = get_trace_id()
                trace_log = create_trace_logger(log, trace_id)
                trace_log.error("critical error in run loop %s", str(e).lower())
            await asyncio.sleep(self.scheduler_interval)

    async def publish_available_scenes(self, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        try:
            payload = {"scenes": list(self.scenes.keys())}
            await self.redis.publish(
                self.pub_chan,
                json.dumps(
                    {
                        "event": "scheduler:available_scenes",
                        "payload": payload,
                        "trace_id": trace_id,
                        "ts": str(dt.now(self.tz)),
                    }
                ),
            )
            trace_log.debug("published scenes to redis chan %s", self.pub_chan)
        except Exception as e:
            trace_log.error(
                "failed to publish available scenes error %s", str(e).lower()
            )

    async def sync_from_redis(self, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        trace_log.info("syncing state from redis")
        await self.handle_mode(trace_id)

    async def handle_power(self, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        try:
            raw = await self.redis.get("system:state")
            if not raw:
                trace_log.warning("handle_power could not find system:state in redis")
                return

            state = json.loads(raw)
            self.runtime.system_on = state.get("system_on", False)
            trace_log.info(
                "power state handled system_on is %s", self.runtime.system_on
            )

            if self.runtime.system_on == True:
                await self.handle_mode(trace_id)
            else:
                await self.deactivate_scene(trace_id)
                self.runtime.cct = 0
                self.runtime.lux = 0
                await self.publish_state(trace_id)
                await self.publish_runtime(trace_id)
        except Exception as e:
            trace_log.error("error in handle_power %s", str(e).lower())
            trace_log.debug(traceback.format_exc().lower())

    async def handle_mode(self, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        try:
            raw = await self.redis.get("system:state")
            if not raw:
                trace_log.warning("handle_mode could not find system:state in redis")
                return

            state = json.loads(raw)
            self.runtime.system_on = state.get("system_on", False)
            self.runtime.mode = state.get("mode", "MANUAL")
            trace_log.info("handling mode change to %s", self.runtime.mode)

            manual = state.get("manual", {})
            auto = state.get("auto", {})

            if self.runtime.mode == "MANUAL":
                await self.deactivate_scene(trace_id)

                manual_lux = manual.get("lux", 0)
                self.runtime.lux = manual_lux
                manual_cw = manual.get("cw")
                manual_ww = manual.get("ww")
                last_toggle = manual.get("last_toggle")

                if last_toggle == "buttons":
                    if manual_cw is not None and manual_ww is not None:
                        await self.apply_manual(
                            "buttons", cw=manual_cw, ww=manual_ww, trace_id=trace_id
                        )
                    else:
                        trace_log.warning(
                            "unable to switch mode with values cw %s ww %s",
                            manual_cw,
                            manual_ww,
                        )
                elif last_toggle == "sliders":
                    await self.apply_manual(
                        "sliders",
                        cct=manual.get("cct", 0),
                        lux=manual_lux,
                        trace_id=trace_id,
                    )

            elif self.runtime.mode == "AUTO":
                self.runtime.loaded_scene = auto.get("loaded_scene")
                self.runtime.running_scene = auto.get("running_scene")
                trace_log.debug(
                    "auto mode state loaded_scene %s running_scene %s",
                    self.runtime.loaded_scene,
                    self.runtime.running_scene,
                )

                if self.runtime.loaded_scene:
                    await self.load_scene(self.runtime.loaded_scene, trace_id)

                if self.runtime.running_scene:
                    await self.interpolator.compute_current_values()
                    res = self.channeler.resolve_channels(
                        self.runtime.cct, self.runtime.lux
                    )
                    if res:
                        self.runtime.cw, self.runtime.ww = res["cw"], res["ww"]

            await self.publish_state(trace_id)
            await self.publish_runtime(trace_id)
        except Exception as e:
            trace_log.error("error in handle_mode %s", str(e).lower())
            trace_log.debug(traceback.format_exc().lower())

    async def load_scene(self, scene_name: str, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        try:
            if scene_name not in self.scenes:
                trace_log.error("scene not found %s", scene_name)
                return

            self.runtime.loaded_scene = scene_name
            scene = self.scenes.get(scene_name)
            serializable_points = [
                {**point, "time": point["time"].strftime("%H:%M")} for point in scene
            ]

            await self.redis.publish(
                self.pub_chan,
                json.dumps(
                    {
                        "event": "scheduler:scene_load",
                        "payload": {
                            "loaded_scene": scene_name,
                            "points": serializable_points,
                        },
                        "trace_id": trace_id,
                        "ts": str(dt.now(self.tz)),
                    }
                ),
            )
            trace_log.info("successfully loaded scene %s", scene_name)
        except Exception as e:
            trace_log.error(
                "failed to load scene %s error %s", scene_name, str(e).lower()
            )

    async def activate_scene(self, scene_name: str, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        try:
            if scene_name not in self.scenes:
                trace_log.error("cannot activate missing scene %s", scene_name)
                return

            if self.runtime.mode != "AUTO":
                trace_log.info(
                    "ignoring activation of %s because mode is not auto", scene_name
                )
                return

            await self.deactivate_scene(trace_id)
            await self.load_scene(scene_name, trace_id)
            self.runtime.running_scene = scene_name
            self.runtime.progress = 0.0

            await self.interpolator.compute_current_values()
            await self.publish_state(trace_id)
            await self.publish_runtime(trace_id)
            trace_log.info("scene %s activated", scene_name)
        except Exception as e:
            trace_log.error(
                "error activating scene %s error %s", scene_name, str(e).lower()
            )

    async def deactivate_scene(self, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        try:
            if not self.runtime.running_scene:
                return
            trace_log.info("deactivating scene %s", self.runtime.running_scene)
            self.runtime.loaded_scene = None
            self.runtime.running_scene = None
            self.runtime.progress = 0.0
            await self.publish_state(trace_id)
        except Exception as e:
            trace_log.error("error deactivating scene %s", str(e).lower())

    async def apply_manual(
        self,
        medium: str,
        cct: float | None = None,
        lux: float | None = None,
        cw: int | None = None,
        ww: int | None = None,
        trace_id=None,
    ):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        try:
            if medium == "sliders":
                if cct is None or lux is None:
                    trace_log.warning("manual sliders applied with missing cct or lux")
                    return
                self.runtime.cct = cct
                self.runtime.lux = lux
                self.runtime.progress = 0.0
                trace_log.debug("applying manual sliders cct %s lux %s", cct, lux)
                result = self.channeler.resolve_channels(
                    self.runtime.cct, self.runtime.lux
                )
                if result:
                    self.runtime.cw, self.runtime.ww = result["cw"], result["ww"]
                    trace_log.debug(
                        "calculated manual values from sliders cw %s ww %s",
                        self.runtime.cw,
                        self.runtime.ww,
                    )

            elif medium == "buttons":
                if cw is None or ww is None:
                    trace_log.warning("manual buttons applied with missing cw or ww")
                    return
                trace_log.debug("applying manual buttons cw %s ww %s", cw, ww)
                result = self.channeler.resolve_cct(cw, ww)
                if not result:
                    return
                self.runtime.cct = result["cct"]
                self.runtime.progress = 0.0
                chan_result = self.channeler.resolve_channels(
                    self.runtime.cct, self.runtime.lux
                )
                if chan_result:
                    self.runtime.cw, self.runtime.ww = (
                        chan_result["cw"],
                        chan_result["ww"],
                    )
                    trace_log.debug(
                        "calculated manual values from buttons cct %s cw %s ww %s",
                        self.runtime.cct,
                        self.runtime.cw,
                        self.runtime.ww,
                    )
        except Exception as e:
            trace_log.error(
                "error applying manual settings via %s error %s", medium, str(e).lower()
            )
            trace_log.debug(traceback.format_exc().lower())
