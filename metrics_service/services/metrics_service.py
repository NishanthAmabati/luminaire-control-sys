import asyncio
import json
import logging
import time
import psutil
from redis.asyncio import Redis

# using a specific name for easier filtering in grafana/loki
log = logging.getLogger("services.metrics_service")

class MetricsService:
    def __init__(self, redis_url: str, channel: str, interval_s: float):
        self.redis = Redis.from_url(redis_url)
        self.channel = channel
        self.interval_s = interval_s
        self.running = True

        # prime cpu_percent for non-blocking reads
        try:
            psutil.cpu_percent(interval=None)
            log.debug("cpu metrics primed")
        except Exception:
            log.exception("failed to prime cpu metrics")

    def _read_temperature_sys(self):
        """primary method for raspberry pi soc temperature"""
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                # convert millidegrees to celsius
                return float(f.read().strip()) / 1000.0
        except Exception:
            return None

    def _read_temperature(self):
        """fallback method using psutil sensors"""
        try:
            # check sysfs first (pi specific)
            temp = self._read_temperature_sys()
            if temp is not None:
                return temp

            # fallback to psutil for other linux distros
            temps = psutil.sensors_temperatures()
            if temps:
                for _, entries in temps.items():
                    for entry in entries:
                        if entry.current:
                            return float(entry.current)
        except Exception:
            log.debug("temperature sensors unavailable")
        return None

    def collect(self):
        metrics = {
            "cpu": None,
            "memory": None,
            "temperature": None
        }

        try:
            metrics["cpu"] = float(psutil.cpu_percent(interval=None))
        except Exception:
            log.exception("failed to collect cpu metrics")

        try:
            metrics["memory"] = float(psutil.virtual_memory().percent)
        except Exception:
            log.exception("failed to collect memory metrics")

        try:
            metrics["temperature"] = self._read_temperature()
        except Exception:
            log.debug("failed to collect temperature metrics")

        return metrics

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
            # using debug to avoid filling loki with heartbeats
            log.debug(f"metrics published to {self.channel}")
        except Exception:
            log.exception(f"failed to publish metrics to channel {self.channel}")

    async def run(self):
        log.info(f"metrics service started with interval {self.interval_s}s")
        while self.running:
            try:
                payload = self.collect()
                await self.publish(payload)
            except Exception:
                log.exception("unexpected error in metrics collection loop")
            
            await asyncio.sleep(self.interval_s)

    async def shutdown(self):
        log.info("shutting down metrics service")
        self.running = False
        try:
            await self.redis.close()
            log.info("metrics service stopped")
        except Exception:
            log.exception("failed to close redis connection during shutdown")