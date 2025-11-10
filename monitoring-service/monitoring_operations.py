import asyncio
import logging
import time
import threading
import yaml
import redis
import pickle
import psutil
import structlog
import uuid

# Load config
with open("/app/config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Structured logging setup (to STDOUT ONLY)
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
logging.basicConfig(
    level=getattr(logging, config["logging"]["level"]),
    format="%(message)s",
    handlers=[logging.StreamHandler()]
)
logger = structlog.get_logger(service="monitoring-operations")

redis_client = redis.Redis(
    host=config["redis"]["host"],
    port=config["redis"]["port"],
    db=config["redis"]["db"],
    password=config["redis"]["password"]
)

class MonitoringOperations:
    def __init__(self):
        self._state_lock = threading.Lock()
        self.update_interval = config.get("monitoring", {}).get("update_interval", 1.0)
        self.state = {
            "cpu_percent": 0.0,
            "mem_percent": 0.0,
            "temperature": None
        }
        self.last_reported = {
            "cpu_percent": None,
            "mem_percent": None,
            "temperature": None
        }
        logger.debug("MonitoringOperations initialized", correlation_id=str(uuid.uuid4()))

    def get_system_stats(self):
        correlation_id = str(uuid.uuid4())
        logger.debug("Fetching system stats", correlation_id=correlation_id)
        try:
            cpu_percent = psutil.cpu_percent(interval=None)
            mem_percent = psutil.virtual_memory().percent
            temperature = None
            try:
                temps = psutil.sensors_temperatures()
                for sensor in ['coretemp', 'k10temp', 'cpu_thermal']:
                    if sensor in temps and temps[sensor]:
                        temperature = temps[sensor][0].current
                        break
                if temperature is None:
                    logger.debug("No temperature sensor data available", correlation_id=correlation_id)
                else:
                    logger.debug("Temperature fetched", correlation_id=correlation_id, temperature=temperature)
            except (AttributeError, NotImplementedError):
                logger.warning("Temperature monitoring not supported", correlation_id=correlation_id)
            return cpu_percent, mem_percent, temperature
        except Exception as e:
            logger.error("Error fetching system stats", correlation_id=correlation_id, error=str(e))
            return 0.0, 0.0, None

    def update_stats_redis(self):
        correlation_id = str(uuid.uuid4())
        with self._state_lock:
            try:
                cpu_percent, mem_percent, temperature = self.get_system_stats()
                self.state["cpu_percent"], self.state["mem_percent"], self.state["temperature"] = cpu_percent, mem_percent, temperature
                redis_client.set("cpu_percent", str(self.state["cpu_percent"]))
                redis_client.set("mem_percent", str(self.state["mem_percent"]))
                redis_client.set("temperature", str(self.state["temperature"]) if self.state["temperature"] is not None else "null")
                stats_msg = pickle.dumps(self.state)
                redis_client.publish("system_stats_update", stats_msg)

                # Log only significant changes
                should_log_info = (
                    self.last_reported["cpu_percent"] is None or
                    abs(self.state["cpu_percent"] - self.last_reported["cpu_percent"]) > 1.0 or
                    abs(self.state["mem_percent"] - self.last_reported["mem_percent"]) > 1.0 or
                    (self.state["temperature"] is not None and
                     (self.last_reported["temperature"] is None or
                      abs(self.state["temperature"] - self.last_reported["temperature"]) > 0.5)) or
                    (self.state["temperature"] is None and self.last_reported["temperature"] is not None)
                )
                if should_log_info:
                    logger.info(
                        "Updated system stats",
                        correlation_id=correlation_id,
                        cpu_percent=self.state["cpu_percent"],
                        mem_percent=self.state["mem_percent"],
                        temperature=self.state["temperature"]
                    )
                    self.last_reported["cpu_percent"] = self.state["cpu_percent"]
                    self.last_reported["mem_percent"] = self.state["mem_percent"]
                    self.last_reported["temperature"] = self.state["temperature"]
                else:
                    logger.debug(
                        "System stats updated",
                        correlation_id=correlation_id,
                        cpu_percent=self.state["cpu_percent"],
                        mem_percent=self.state["mem_percent"],
                        temperature=self.state["temperature"]
                    )
            except Exception as e:
                logger.error("Error updating Redis stats", correlation_id=correlation_id, error=str(e))

    async def broadcast_system_stats(self):
        correlation_id = str(uuid.uuid4())
        logger.info("Starting system stats broadcast", correlation_id=correlation_id)
        while True:
            self.update_stats_redis()
            await asyncio.sleep(self.update_interval)