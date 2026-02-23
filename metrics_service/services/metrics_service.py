import asyncio
import json
import logging
import os
import time

import psutil
from redis.asyncio import Redis

log = logging.getLogger(__name__)

class MetricsService:
    def __init__(self, redis_url: str, channel: str, interval_s: float):
        self.redis = Redis.from_url(redis_url)
        self.channel = channel
        self.interval_s = interval_s
        self.running = True

        # Prime cpu_percent so subsequent reads are non-blocking.
        try:
            psutil.cpu_percent(interval=None)
        except Exception:
            log.exception("Failed to prime cpu_percent")

    def _read_temperature_sys(self):
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                return float(f.read()) / 1000.0
        except Exception:
            return None

    def _read_temperature(self):
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for _, entries in temps.items():
                    for entry in entries:
                        if entry.current is not None:
                            return float(entry.current)
        except Exception:
            log.debug("psutil.sensors_temperatures unavailable")
        return self._read_temperature_sys()

    def collect(self):
        cpu = None
        memory = None
        temperature = None

        try:
            cpu = float(psutil.cpu_percent(interval=None))
        except Exception:
            log.exception("Failed to read cpu percent")

        try:
            memory = float(psutil.virtual_memory().percent)
        except Exception:
            log.exception("Failed to read memory percent")

        temperature = self._read_temperature()

        return {
            "cpu": cpu,
            "memory": memory,
            "temperature": temperature,
        }

    async def publish(self, payload: dict):
        try:
            await self.redis.publish(
                self.channel,
                json.dumps({
                    "event": "metrics:events",
                    "payload": payload,
                    "ts": time.time()
                })
            )
        except Exception as e:
            log.exception(f"failed to publish metrics to redis. err: {e}")

    async def run(self):
        log.info("metrics service started")
        while self.running:
            payload = self.collect()
            await self.publish(payload)
            await asyncio.sleep(self.interval_s)

    async def shutdown(self):
        self.running = False
        try:
            await self.redis.close()
            await self.redis.connection_pool.disconnect()
        except Exception:
            log.exception("Failed to close redis")
