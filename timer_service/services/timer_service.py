import json
import pytz
import structlog
import logging

from datetime import datetime
from models.timer_runtime import TimerRuntime
from services.scheduler import Scheduler
from clients.state_client import StateClient

log = structlog.get_logger()
logging.getLogger('apscheduler').setLevel(logging.DEBUG)

class TimerService:

    def __init__(self, redis_url, pub_chan, tz, state_service_url):
        self.redis = redis_url
        self.pub_chan = pub_chan
        self.tz = pytz.timezone(tz)
        self.state_client = StateClient(state_service_url)
        self.scheduler = Scheduler(self.tz, self.state_client)
        self.runtime = TimerRuntime()
        self._task = None

    async def publish_state(self):
        try:
            payload = {
                "timer_enabled": self.runtime.timer_enabled,
                "timer_start": self.runtime.timer_start,
                "timer_end": self.runtime.timer_end
            }
            await self.redis.publish(
                self.pub_chan, # timer:events
                json.dumps({
                    "event": "timer:state",
                    "payload": payload,
                    "ts": str(datetime.now(self.tz))
                })
            )
            log.debug("timer_state_published", payload=payload)
        except Exception as e:
            log.error("redis_publish_failed", channel=self.pub_chan, error=str(e), exc_info=True)

    async def sync_from_redis(self):
        try:
            raw = await self.redis.get("system:state")
            if not raw:
                log.warning("timer_sync_skipped", reason="state_not_found_in_redis", key="system:state")
                return
            
            state = json.loads(raw)
            timer_state = state.get("timer", {})
            self.runtime.timer_enabled = timer_state.get("enabled")
            self.runtime.timer_start = timer_state.get("start")
            self.runtime.timer_end = timer_state.get("end")
            
            if self.runtime.timer_enabled:
                self.scheduler.start()
                self.scheduler.configure(self.runtime.timer_start, self.runtime.timer_end)
                
            log.info("timer_synced_from_redis", enabled=self.runtime.timer_enabled, start=self.runtime.timer_start, end=self.runtime.timer_end)
            await self.publish_state()
        except Exception as e:
            log.error("timer_sync_failed", error=str(e), exc_info=True)

    async def run(self):
        log.info("timer_service_running")
        self.scheduler.start()

    async def shutdown(self):
        log.info("timer_service_shutting_down")
        self.scheduler.shutdown()

    async def toggle_timer(self, payload=None):
        try:
            enabled = payload.get("enabled") if payload else None
            if enabled is None:
                raw = await self.redis.get("system:state")
                if raw:
                    state = json.loads(raw)
                    enabled = state.get("timer", {}).get("enabled")

            self.runtime.timer_enabled = enabled

            if self.runtime.timer_enabled and self.runtime.timer_start and self.runtime.timer_end:
                self.scheduler.start()
                self.scheduler.configure(self.runtime.timer_start, self.runtime.timer_end)
            else:
                self.scheduler.clear_jobs()
                
            await self.publish_state()
        except Exception as e:
            log.error("timer_toggle_failed", error=str(e), exc_info=True)

    async def configure_timer(self, payload=None):
        try:
            start = payload.get("start") if payload else None
            end = payload.get("end") if payload else None

            if not self.runtime.timer_enabled:
                log.info("timer_config_skipped", reason="timer_not_enabled", enabled=self.runtime.timer_enabled)
                return

            if start:
                self.runtime.timer_start = start
            if end:
                self.runtime.timer_end = end
            
            if self.runtime.timer_enabled:
                self.scheduler.start()
                self.scheduler.configure(self.runtime.timer_start, self.runtime.timer_end)
                
            await self.publish_state()
        except Exception as e:
            log.error("timer_configure_failed", error=str(e), exc_info=True)
            
    async def clear_timer(self, payload=None):
        try:
            self.runtime.timer_enabled = False
            self.runtime.timer_start = None
            self.runtime.timer_end = None

            self.scheduler.clear_jobs()
            await self.publish_state()
        except Exception as e:
            log.error("timer_clear_failed", error=str(e), exc_info=True)