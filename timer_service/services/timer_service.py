import asyncio
import json
import logging
import pytz
from datetime import datetime

from utilities.tracing import create_trace_logger
from utilities.trace_context import get_trace_id

log = logging.getLogger("services.timer_service")


class TimerService:
    def __init__(self, redis_url, pub_chan, tz, state_service_url):
        self.redis = redis_url
        self.pub_chan = pub_chan
        self.tz = pytz.timezone(tz)

        from clients.state_client import StateClient
        from services.scheduler import Scheduler
        from models.timer_runtime import TimerRuntime

        self.state_client = StateClient(state_service_url)
        self.scheduler = Scheduler(self.tz, self.state_client)
        self.runtime = TimerRuntime()

    async def publish_state(self, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        try:
            payload = {
                "timer_enabled": self.runtime.timer_enabled,
                "timer_start": self.runtime.timer_start,
                "timer_end": self.runtime.timer_end,
            }
            await self.redis.publish(
                self.pub_chan,
                json.dumps(
                    {
                        "event": "timer:state_sync",
                        "payload": payload,
                        "trace_id": trace_id,
                        "ts": datetime.now(self.tz).isoformat(),
                    }
                ),
            )
            trace_log.debug("timer state published to redis")
        except Exception:
            trace_log.exception(
                "failed to publish timer state to channel %s", self.pub_chan
            )

    async def _update_runtime_from_state(self, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        try:
            raw = await self.redis.get("system:state")
            if not raw:
                trace_log.warning(
                    "system state not found in redis - using existing runtime"
                )
                return False

            state = json.loads(raw)
            timer_cfg = state.get("timer", {})

            self.runtime.timer_enabled = timer_cfg.get("enabled", False)
            self.runtime.timer_start = timer_cfg.get("start")
            self.runtime.timer_end = timer_cfg.get("end")
            return True
        except Exception:
            trace_log.exception("failed to parse system state from redis")
            return False

    async def sync_from_redis(self, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        trace_log.info("syncing timer runtime from redis state")
        if await self._update_runtime_from_state(trace_id):
            if (
                self.runtime.timer_enabled
                and self.runtime.timer_start
                and self.runtime.timer_end
            ):
                self.scheduler.start()
                self.scheduler.configure(
                    self.runtime.timer_start, self.runtime.timer_end
                )
                trace_log.info(
                    "timer synced and active: %s - %s",
                    self.runtime.timer_start,
                    self.runtime.timer_end,
                )
            else:
                trace_log.info("timer synced but remains inactive or unconfigured")

            await self.publish_state(trace_id)

    async def run(self):
        log.info("starting timer service main scheduler")
        self.scheduler.start()

    async def shutdown(self):
        trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        trace_log.info("shutting down timer service components")
        try:
            self.scheduler.shutdown()
            trace_log.info("timer service components stopped")
        except Exception:
            trace_log.exception("error during timer service shutdown")

    async def toggle_timer(self, enabled: bool, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        trace_log.info("processing timer toggle: %s", enabled)
        if await self._update_runtime_from_state(trace_id):
            if (
                self.runtime.timer_enabled
                and self.runtime.timer_start
                and self.runtime.timer_end
            ):
                self.scheduler.start()
                self.scheduler.configure(
                    self.runtime.timer_start, self.runtime.timer_end
                )
            else:
                self.scheduler.clear_jobs()
            await self.publish_state(trace_id)

    async def configure_timer(self, start=None, end=None, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        trace_log.info("processing timer reconfiguration: %s to %s", start, end)
        if await self._update_runtime_from_state(trace_id):
            if not self.runtime.timer_enabled:
                trace_log.debug("skipping scheduler configuration as timer is disabled")
                return

            if self.runtime.timer_start and self.runtime.timer_end:
                self.scheduler.start()
                self.scheduler.configure(
                    self.runtime.timer_start, self.runtime.timer_end
                )
                await self.publish_state(trace_id)
            else:
                trace_log.warning(
                    "reconfiguration failed: start or end time missing in state"
                )

    async def clear_timer(self, trace_id=None):
        if not trace_id:
            trace_id = get_trace_id()
        trace_log = create_trace_logger(log, trace_id)
        trace_log.info("clearing timer schedule")
        if await self._update_runtime_from_state(trace_id):
            self.scheduler.clear_jobs()
            trace_log.info("scheduler jobs purged")
            await self.publish_state(trace_id)
