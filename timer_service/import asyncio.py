import asyncio
import json
import logging
import psutil
import time

from datetime import datetime
from redis.asyncio import Redis

from models.metrics_runtime import MetricsRuntime

log = logging.getLogger(__name__)

class MetricsService:

    def __init__(
        self,
        redis_url: str,
        pub_chan: str,
        interval: int = 5,
        timezone=None
    ):
        self.redis = Redis.from_url(redis_url)
        self.pub_chan = pub_chan
        self.interval = interval
        self.runtime = MetricsRuntime()
        self._task = None
        self._running = False
        self._start_time = time.time()
        self.tz = timezone

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._loop())
        log.info("metrics service started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        await self.redis.close()
        log.info("metrics service stopped")

    async def _loop(self):
        while self._running:
            try:
                await self.collect_metrics()
                await self.publish()
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("metrics loop error")
                await asyncio.sleep(self.interval)

    async def collect_metrics(self):
        try:
            self.runtime.cpu = psutil.cpu_percent(interval=None)
            self.runtime.memory = psutil.virtual_memory() #.percent
            self.runtime.temperature = self._get_cpu_temp()
        except Exception as e:
            log.exception(f"failed to collect metrics, err: {e}")

    async def publish(self):
        try:
            payload = {
                "cpu": self.runtime.cpu_percent,
                "memory": self.runtime.mem_percent,
                "temperature": self.runtime.cpu_temp,
            }

            await self.redis.publish(
                self.pub_chan,
                json.dumps({
                    "event": "metrics:update",
                    "payload": payload,
                })
            )
        except Exception as e:
            log.exception(f"failed to publish metrics, err: {e}")

    def _get_cpu_temp(self):
        try:
            temps = psutil.sensors_temperatures()
            if not temps:
                return None

            # Common Linux key
            for name, entries in temps.items():
                for entry in entries:
                    if entry.current:
                        return entry.current

            return None

        except Exception:
            return None
