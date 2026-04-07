import asyncio
import logging
import json
import time

from redis.asyncio import Redis
from models.state import SystemState
from utils.tracing import create_trace_logger
from utils.trace_context import get_trace_id

log = logging.getLogger("services.state_service")


class StateService:
    def __init__(self, redisURL: str, state_key: str, channel: str):
        self.lock = asyncio.Lock()
        self.redis = Redis.from_url(redisURL)
        self.state_key = state_key
        self.channel = channel
        self.state = SystemState()

    async def load(self):
        try:
            state_from_redis = await self.redis.get(self.state_key)
            if state_from_redis:
                self.state = SystemState.from_dict(json.loads(state_from_redis))
                log.info("state restored from redis")
            else:
                log.info("no previous state found, using default values")
        except Exception:
            log.exception(f"failed to load state from key {self.state_key}")

    async def persist(self, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        try:
            await self.redis.set(self.state_key, json.dumps(self.state.to_dict()))
            trace_log.debug("state persisted successfully")
        except Exception:
            trace_log.exception(f"failed to persist state to key {self.state_key}")

    async def publish(self, event: str, payload: dict, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        try:
            await self.redis.publish(
                self.channel,
                json.dumps(
                    {
                        "event": event,
                        "payload": payload,
                        "trace_id": trace_id,
                        "ts": time.time(),
                    }
                ),
            )
            trace_log.debug("event %s published to %s", event, self.channel)
        except Exception:
            trace_log.exception("failed to publish event %s to redis", event)

    async def get_state(self) -> SystemState:
        async with self.lock:
            return self.state

    async def set_system_power(self, on: bool, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        try:
            async with self.lock:
                self.state.system_on = on
                trace_log.info("system power toggled to %s", on)
                self.state.touch()
                await self.persist(trace_id)
            await self.publish("system:power", {"on": on}, trace_id)
        except Exception:
            trace_log.exception("failed to toggle system power to %s", on)

    async def set_mode(self, mode: str, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        try:
            async with self.lock:
                self.state.mode = mode
                trace_log.info("system mode switched to %s", mode)
                self.state.touch()
                await self.persist(trace_id)
            await self.publish("system:mode", {"mode": mode}, trace_id)
        except Exception:
            trace_log.exception("failed to switch system mode to %s", mode)

    async def update_metrics(
        self,
        cpu: float | None,
        memory: float | None,
        temperature: float | None,
        trace_id=None,
    ):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        try:
            async with self.lock:
                if cpu is not None:
                    self.state.metrics.cpu = cpu
                if memory is not None:
                    self.state.metrics.memory = memory
                if temperature is not None:
                    self.state.metrics.temperature = temperature
                self.state.touch()
                await self.persist(trace_id)
            trace_log.debug("system metrics updated in state")
        except Exception:
            trace_log.exception("failed to update system metrics")

    async def set_manual_values(
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
        pub_message = {}
        try:
            async with self.lock:
                if medium == "sliders":
                    self.state.manual.last_toggle = "sliders"
                    self.state.manual.cct = cct
                    self.state.manual.lux = lux
                    pub_message = {"medium": "sliders", "cct": cct, "lux": lux}
                    trace_log.info("manual update via sliders: cct %s lux %s", cct, lux)
                elif medium == "buttons":
                    self.state.manual.last_toggle = "buttons"
                    self.state.manual.cw = cw
                    self.state.manual.ww = ww
                    pub_message = {"medium": "buttons", "cw": cw, "ww": ww}
                    trace_log.info("manual update via buttons: cw %s ww %s", cw, ww)
                else:
                    trace_log.warning(
                        "ignored manual update with unknown medium %s", medium
                    )
                    return
                self.state.touch()
                await self.persist(trace_id)
            await self.publish("manual:update", pub_message, trace_id)
        except Exception:
            trace_log.exception("failed to process manual update via %s", medium)

    async def update_auto_runtime(
        self, cct: float, lux: float, progress: float, trace_id=None
    ):
        if not trace_id:
            trace_id = get_trace_id()
        async with self.lock:
            self.state.auto.cct = cct
            self.state.auto.lux = lux
            self.state.auto.scene_progress = progress
            self.state.touch()
            await self.persist(trace_id)

    async def load_scene(self, scene: str, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        try:
            async with self.lock:
                self.state.auto.loaded_scene = scene
                trace_log.info("scene loaded %s", scene)
                self.state.touch()
                await self.persist(trace_id)
            await self.publish("scheduler:scene_loaded", {"scene": scene}, trace_id)
        except Exception:
            trace_log.exception("failed to load scene %s", scene)

    async def activate_scene(self, scene: str, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        try:
            async with self.lock:
                self.state.auto.loaded_scene = scene
                self.state.auto.running_scene = scene
                trace_log.info("scene activated %s", scene)
                self.state.touch()
                await self.persist(trace_id)
            await self.publish("scheduler:scene_activated", {"scene": scene}, trace_id)
        except Exception:
            trace_log.exception("failed to activate scene %s", scene)

    async def deactivate_scene(self, scene: str, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        try:
            async with self.lock:
                self.state.auto.loaded_scene = None
                self.state.auto.running_scene = None
                self.state.auto.scene_progress = 0.0
                trace_log.info("scene deactivated %s", scene)
                self.state.touch()
                await self.persist(trace_id)
            await self.publish("scheduler:scene_stopped", {}, trace_id)
        except Exception:
            trace_log.exception("failed to deactivate scene %s", scene)

    async def request_available_scenes(self, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        try:
            await self.publish("scheduler:available_scenes", {}, trace_id)
            trace_log.debug("requested available scenes from scheduler")
        except Exception:
            trace_log.exception("failed to request available scenes")

    async def toggle_timer(self, enabled: bool, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        try:
            async with self.lock:
                self.state.timer.enabled = enabled
                trace_log.info("timer toggled to %s", enabled)
                self.state.touch()
                await self.persist(trace_id)
            await self.publish("timer:toggled", {"enabled": enabled}, trace_id)
        except Exception:
            trace_log.exception("failed to toggle timer to %s", enabled)

    async def configure_timer(self, start, end, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        try:
            async with self.lock:
                self.state.timer.start = start
                self.state.timer.end = end
                trace_log.info("timer configured from %s to %s", start, end)
                self.state.touch()
                await self.persist(trace_id)
            await self.publish(
                "timer:configured", {"start": str(start), "end": str(end)}, trace_id
            )
        except Exception:
            trace_log.exception("failed to configure timer for range %s-%s", start, end)

    async def clear_timer(self, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        try:
            async with self.lock:
                self.state.timer.enabled = False
                self.state.timer.start = None
                self.state.timer.end = None
                trace_log.info("timer state cleared")
                self.state.touch()
                await self.persist(trace_id)
            await self.publish("timer:cleared", {}, trace_id)
        except Exception:
            trace_log.exception("failed to clear timer state")

    async def shutdown(self):
        try:
            log.info("shutting down state service redis connection")
            await self.redis.close()
            log.info("state service stopped")
        except Exception:
            log.exception("failed to close redis during state service shutdown")
