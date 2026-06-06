import asyncio
import json
import time
import structlog

from redis.asyncio import Redis
from models.state import SystemState

log = structlog.get_logger()

class StateService:
    def __init__(self, redisURL: str, state_key: str, channel: str):
        self.lock = asyncio.Lock()
        self.redis = Redis.from_url(redisURL)
        self.state_key = state_key
        self.channel = channel
        self.state = SystemState()

    async def load(self):
        """Load state from Redis on startup"""
        try:
            state_from_redis = await self.redis.get(self.state_key)
            if state_from_redis:
                self.state = SystemState.from_dict(json.loads(state_from_redis))
                log.info("state_restored_from_redis", state_key=self.state_key)
            else:
                log.info("state_not_found_using_defaults", state_key=self.state_key)
        except Exception as e:
             log.error("state_load_failed", error=str(e), exc_info=True)

    async def persist(self):
        try:
            await self.redis.set(
                self.state_key,
                json.dumps(self.state.to_dict())
            )
        except Exception as e:
            log.error("state_persist_failed", state_key=self.state_key, error=str(e), exc_info=True)

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
            log.debug("redis_publish_success", redis_event=event, payload=payload)
        except Exception as e:
            log.error("redis_publish_failed", redis_event=event, channel=self.channel, error=str(e), exc_info=True)

    async def get_state(self) -> SystemState:
        async with self.lock:
            return self.state

    async def set_system_power(self, on: bool):
        try:
            async with self.lock:
                self.state.system_on = on
                self.state.touch()
                await self.persist()
                
            log.info("system_power_toggled", system_on=on)
            await self.publish("system:power", {"on": on})
        except Exception as e:
            log.error("system_power_toggle_failed", system_on=on, error=str(e), exc_info=True)

    async def set_mode(self, mode: str):
        try:
            async with self.lock:
                self.state.mode = mode
                self.state.touch()
                await self.persist()
                
            log.info("system_mode_changed", mode=mode)
            await self.publish("system:mode", {"mode": mode})
        except Exception as e:
            log.error("system_mode_change_failed", mode=mode, error=str(e), exc_info=True)

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
            log.error("metrics_state_update_failed", error=str(e), exc_info=True)

    async def set_manual_values(self,
                                medium: str,
                                cct: float | None = None,
                                lux: float | None = None,
                                cw: int | None = None,
                                ww: int | None = None
                                ):
        pub_message = {}
        try:
            async with self.lock:
                if medium == "sliders":
                    self.state.manual.last_toggle = "sliders"
                    self.state.manual.cct = cct
                    self.state.manual.lux = lux
                    pub_message = {"medium": "sliders", "cct": cct, "lux": lux}
                    log.info("manual_update_applied", medium="sliders", cct=cct, lux=lux)
                    
                elif medium == "buttons":
                    self.state.manual.last_toggle = "buttons"
                    self.state.manual.cw = cw
                    self.state.manual.ww = ww
                    pub_message = {"medium": "buttons", "cw": cw, "ww": ww}
                    log.info("manual_update_applied", medium="buttons", cw=cw, ww=ww)
                    
                else:
                    log.warning("manual_update_ignored_unknown_medium", medium=medium)
                    return
                    
                self.state.touch()
                await self.persist()
                
            await self.publish("manual:update", pub_message)
        except Exception as e:
            log.error("manual_update_failed", payload=pub_message, error=str(e), exc_info=True)

    async def update_auto_runtime(self, cct: float, lux: float, progress: float):
        try:
            async with self.lock:
                self.state.auto.cct = cct
                self.state.auto.lux = lux
                self.state.auto.scene_progress = progress
                self.state.touch()
                await self.persist()
        except Exception as e:
             log.error("auto_runtime_state_update_failed", error=str(e), exc_info=True)

    async def load_scene(self, scene: str):
        try:
            async with self.lock:
                self.state.auto.loaded_scene = scene
                self.state.touch()
                await self.persist()
                
            log.info("scene_loaded", scene_name=scene)
            await self.publish("scheduler:scene_loaded", {"scene": scene})
        except Exception as e:
            log.error("scene_load_failed", scene_name=scene, error=str(e), exc_info=True)

    async def activate_scene(self, scene: str):
        try:
            async with self.lock:
                self.state.auto.loaded_scene = scene
                self.state.auto.running_scene = scene
                self.state.touch()
                await self.persist()
                
            log.info("scene_activated", scene_name=scene)
            await self.publish("scheduler:scene_activated", {"scene": scene})
        except Exception as e:
            log.error("scene_activation_failed", scene_name=scene, error=str(e), exc_info=True)

    async def deactivate_scene(self, scene: str):
        try:
            async with self.lock:
                self.state.auto.loaded_scene = None
                self.state.auto.running_scene = None
                self.state.auto.scene_progress = 0.0
                self.state.touch()
                await self.persist()
                
            log.info("scene_deactivated", scene_name=scene)
            await self.publish("scheduler:scene_stopped", {})
        except Exception as e:
            log.error("scene_deactivation_failed", scene_name=scene, error=str(e), exc_info=True)

    async def request_available_scenes(self):
        try:
            await self.publish("scheduler:available_scenes", {})
        except Exception as e:
            log.error("available_scenes_request_failed", error=str(e), exc_info=True)
        
    async def toggle_timer(self, enabled: bool):
        try:
            async with self.lock:
                self.state.timer.enabled = enabled
                self.state.touch()
                await self.persist()
                
            log.info("timer_toggled", timer_enabled=enabled)
            await self.publish("timer:toggled", {"enabled": enabled})
        except Exception as e:
            log.error("timer_toggle_failed", timer_enabled=enabled, error=str(e), exc_info=True)

    async def configure_timer(self, start, end):
        try:
            async with self.lock:
                self.state.timer.start = start
                self.state.timer.end = end
                self.state.touch()
                await self.persist()
                
            log.info("timer_configured", timer_start=str(start), timer_end=str(end))
            await self.publish("timer:configured", {"start": start, "end": end})
        except Exception as e:
            log.error("timer_configuration_failed", timer_start=str(start), timer_end=str(end), error=str(e), exc_info=True)

    async def clear_timer(self):
        try:
            async with self.lock:
                self.state.timer.enabled = False
                self.state.timer.start = None
                self.state.timer.end = None
                self.state.touch()
                await self.persist()
                
            log.info("timer_cleared")
            await self.publish("timer:cleared", {})
        except Exception as e:
            log.error("timer_clear_failed", error=str(e), exc_info=True)

    async def shutdown(self):
        log.info("state_service_shutdown_initiated")
        try:
            await self.redis.close()
            await self.redis.connection_pool.disconnect()
            log.info("redis_connection_closed")
        except Exception as e:
            log.error("redis_close_failed", error=str(e), exc_info=True)