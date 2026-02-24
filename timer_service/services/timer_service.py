import asyncio
import json
import logging
import pytz

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from redis.asyncio import Redis
from datetime import datetime
from models.timer_runtime import TimerRuntime
from services.scheduler import Scheduler
from clients.state_client import StateClient

log = logging.getLogger(__name__)

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
                self.pub_chan, #timer:events
                json.dumps({
                    "event": "timer:state",
                    "payload": payload,
                    "ts": str(datetime.now(self.tz))
                })
            )
        except Exception as e:
            log.exception(f"failed to publish timer state to redis, chan: '{self.pub_chan}'")

    async def sync_from_redis(self):
        raw = await self.redis.get("system:state")
        if not raw:
            log.warning("timer sync skipped: system:state not found in redis")
            return
        state = json.loads(raw)
        timer_state = state.get("timer", {})
        self.runtime.timer_enabled = timer_state.get("enabled")
        self.runtime.timer_start = timer_state.get("start")
        self.runtime.timer_end = timer_state.get("end")
        if self.runtime.timer_enabled:
            self.scheduler.start()
            self.scheduler.configure(self.runtime.timer_start, self.runtime.timer_end)
        log.info("sycned timer from redis")
        await self.publish_state()

    async def run(self):
        self.scheduler.start()

    async def shutdown(self):
        self.scheduler.shutdown()

    async def toggle_timer(self):
        raw = await self.redis.get("system:state")
        if not raw:
            return
        state = json.loads(raw)
        timer_state = state.get("timer", {})
        self.runtime.timer_enabled = timer_state.get("enabled")
        self.runtime.timer_start = timer_state.get("start")
        self.runtime.timer_end = timer_state.get("end")
        if self.runtime.timer_enabled and self.runtime.timer_start and self.runtime.timer_end:
            self.scheduler.start()
            self.scheduler.configure(self.runtime.timer_start, self.runtime.timer_end)
        else:
            self.scheduler.clear_jobs()
        await self.publish_state()

    async def configure_timer(self):
        raw = await self.redis.get("system:state")
        if not raw:
            return
        state = json.loads(raw)
        timer_state = state.get("timer", {})
        if not self.runtime.timer_enabled:
            log.info(f"skipped timer config as timer_enabled: {self.runtime.timer_enabled}")
            return
        self.runtime.timer_start = timer_state.get("start")
        self.runtime.timer_end = timer_state.get("end")
        if self.runtime.timer_enabled:
            self.scheduler.start()
            self.scheduler.configure(self.runtime.timer_start, self.runtime.timer_end)
        await self.publish_state()
        
    async def clear_timer(self):
        raw = await self.redis.get("system:state")
        if not raw:
            return
        state = json.loads(raw)
        timer_state = state.get("timer", {})
        self.runtime.timer_enabled = timer_state.get("enabled")
        self.runtime.timer_start = timer_state.get("start")
        self.runtime.timer_end = timer_state.get("end")
        self.scheduler.clear_jobs()
        await self.publish_state()
