import asyncio
import json
import logging
import time

from redis.asyncio import Redis
from models.state import SystemState

log = logging.getLogger(__name__)

class StateService:
    def __init__(self, redisURL: str, state_key: str, channel: str):
        self.lock = asyncio.Lock()
        self.redis = Redis.from_url(redisURL)
        self.state_key = state_key
        self.channel = channel
        self.state = SystemState()

    async def load(self):
        """Load state from Redis on startup"""
        state_from_redis = await self.redis.get(self.state_key)
        if state_from_redis:
            self.state = SystemState.from_dict(json.loads(state_from_redis))
            log.info("state restored from redis")
        else:
            log.info("no previous state found, using defaults")

    async def persist(self):
        try:
            await self.redis.set(
                self.state_key,
                json.dumps(self.state.to_dict())
            )
        except Exception as e:
            log.exception(f"failed to persist state key={self.state_key}. err: {e}")

    async def publish(self, event: str, payload: dict):
        try:
            await self.redis.publish(
                self.channel,
                json.dumps({
                    "event": event,
                    "payload": payload,
                    "ts": time.time()
                })
            )
        except Exception as e:
            log.exception(f"failed to publish event '{event}' to redis. err: {e}")

    async def get_state(self) -> SystemState:
        async with self.lock:
            return self.state

    async def set_system_power(self, on: bool):
        try:
            async with self.lock:
                self.state.system_on = on
                log.info(f"system power toggled {on}")
                self.state.touch()
                await self.persist()
            await self.publish("system:power", {"on": on})
        except Exception as e:
            log.exception(f"failed to toggle system power {on}. err: {e}")

    async def set_mode(self, mode: str):
        try:
            async with self.lock:
                self.state.mode = mode
                log.info(f"system mode switched to {mode}")
                self.state.touch()
                await self.persist()
            await self.publish("system:mode", {"mode": mode})
        except Exception as e:
            log.exception(f"failed to switch system mode to {mode}. err: {e}")

    async def update_metrics(self, cpu: float | None, memory: float | None, temperature: float | None):
        try:
            async with self.lock:
                if cpu is not None:
                    self.state.metrics.cpu = cpu
                if memory is not None:
                    self.state.metrics.memory = memory
                if temperature is not None:
                    self.state.metrics.temperature = temperature
                self.state.touch()
                await self.persist()
        except Exception as e:
            log.exception(f"failed to update metrics.* cpu, memory, temperature. err: {e}")

    async def set_manual_values(self,
                                medium: str,
                                cct: float | None = None,
                                lux: float | None = None,
                                cw: int | None = None,
                                ww: int | None = None
                                ):
        try:
            async with self.lock:
                if medium == "sliders":
                    self.state.manual.last_toggle = "sliders"
                    self.state.manual.cct = cct
                    self.state.manual.lux = lux
                    pub_message = {"medium": "sliders", "cct": cct, "lux": lux}
                    log.info(f"manual update: cct: {cct}, lux: {lux}")
                elif medium == "buttons":
                    self.state.manual.last_toggle = "buttons"
                    self.state.manual.cw = cw
                    self.state.manual.ww = ww
                    pub_message = {"medium": "buttons", "cw": cw, "ww": ww}
                    log.info(f"manual update: cw: {cw}, ww: {ww}")
                else:
                    log.warning(f"ignored manual update with unknown medium: {medium}")
                    return
                self.state.touch()
                await self.persist()
            await self.publish(
                "manual:update",
                pub_message
            )
        except Exception as e:
            log.exception(f"failed manual update: {pub_message}. err: {e}")

    async def update_auto_runtime(self, cct: float, lux: float, progress: float):
        async with self.lock:
            self.state.auto.cct = cct
            self.state.auto.lux = lux
            self.state.auto.scene_progress = progress
            self.state.touch()
            await self.persist()
            '''        await self.publish(
                        "scheduler:runtime",
                        {"cct": cct, "lux": lux, "progress": progress}
                    )'''
    
    async def load_scene(self, scene: str):
        try:
            async with self.lock:
                self.state.auto.loaded_scene = scene
                log.info(f"scene loaded: {scene}")
                self.state.touch()
                await self.persist()
            await self.publish(
                "scheduler:scene_loaded",
                {"scene": scene}
            )
        except Exception as e:
            log.exception(f"failed to load scene {scene}. err: {e}")

    async def activate_scene(self, scene: str):
        try:
            async with self.lock:
                self.state.auto.loaded_scene = scene
                self.state.auto.running_scene = scene
                log.info(f"scene activated: {scene}")
                self.state.touch()
                await self.persist()
            await self.publish(
                "scheduler:scene_activated",
                {"scene": scene}
            )
        except Exception as e:
            log.exception(f"failed to activate scene {scene}. err: {e}")

    async def deactivate_scene(self, scene: str):
        try:
            async with self.lock:
                self.state.auto.loaded_scene = None
                self.state.auto.running_scene = None
                self.state.auto.scene_progress = 0.0
                log.info(f"scene deactivated: {scene}")
                self.state.touch()
                await self.persist()
            await self.publish(
                "scheduler:scene_stopped",
                {}
            )
        except Exception as e:
            log.exception(f"failed to deactivate scene {scene}. err: {e}")

    async def request_available_scenes(self):
        try:
            await self.publish(
                "scheduler:available_scenes",
                {}
            )
        except Exception as e:
            log.exception(f"failed to request available scenes. err: {e}")
        
    async def toggle_timer(self, enabled: bool):
        try:
            async with self.lock:
                self.state.timer.enabled = enabled
                log.info(f"timer toggled {enabled}")
                self.state.touch()
                await self.persist()
            await self.publish(
                "timer:toggled",
                {"enabled": enabled}
            )
        except Exception as e:
            log.exception(f"failed to toggle system timer {enabled}. err: {e}")

    async def configure_timer(self, start: time, end: time):
        try:
            async with self.lock:
                self.state.timer.start = start
                self.state.timer.end = end
                log.info(f"timer configured, start: {start}, end: {end}")
                self.state.touch()
                await self.persist()
            await self.publish(
                "timer:configured",
                {
                    "start": start,
                    "end": end
                    }
            )
        except Exception as e:
            log.exception(f"failed to configure timer: start: {start}, end: {end}. err: {e}")

    async def clear_timer(self):
        try:
            async with self.lock:
                self.state.timer.enabled = False
                self.state.timer.start = None
                self.state.timer.end = None
                log.info("timer state cleared")
                self.state.touch()
                await self.persist()
            await self.publish("timer:cleared", {})
        except Exception as e:
            log.exception(f"failed to clear timer state. err: {e}")

    async def shutdown(self):
        try:
            log.info("stopping redis...")
            await self.redis.close()
            await self.redis.connection_pool.disconnect()
            log.info("stopped redis")
        except Exception:
            log.exception("failed to close redis")
