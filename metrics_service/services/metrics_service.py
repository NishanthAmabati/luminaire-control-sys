import asyncio
import json
import time
import psutil
import structlog
from redis.asyncio import Redis

log = structlog.get_logger()

class MetricsService:
    def __init__(self, redis_url: str, channel: str, interval_s: float):
        self.redis = Redis.from_url(redis_url)
        self.channel = channel
        self.interval_s = interval_s
        self.running = True

        try:
            psutil.cpu_percent(interval=None)
        except Exception as e:
            log.error("cpu_percent_prime_failed", error=str(e), exc_info=True)

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
            log.debug("psutil_sensors_temperatures_unavailable")
        return self._read_temperature_sys()

    def collect(self):
        cpu = None
        memory = None
        temperature = None

        try:
            cpu = float(psutil.cpu_percent(interval=None))
        except Exception as e:
            log.error("metric_collection_failed", metric="cpu", error=str(e), exc_info=True)

        try:
            memory = float(psutil.virtual_memory().percent)
        except Exception as e:
            log.error("metric_collection_failed", metric="memory", error=str(e), exc_info=True)

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
            log.debug("metrics_published", channel=self.channel, payload=payload)
        except Exception as e:
            log.error("redis_publish_failed", event="metrics:events", channel=self.channel, error=str(e), exc_info=True)

    async def run(self):
        log.info("metrics_collection_started", interval_s=self.interval_s)
        while self.running:
            payload = self.collect()
            await self.publish(payload)
            await asyncio.sleep(self.interval_s)

    async def shutdown(self):
        log.info("metrics_service_shutdown_initiated")
        self.running = False
        try:
            await self.redis.close()
            await self.redis.connection_pool.disconnect()
            log.info("redis_connection_closed")
        except Exception as e:
            log.error("redis_close_failed", error=str(e), exc_info=True)