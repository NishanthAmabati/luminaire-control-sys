import asyncio
import logging
import time
import threading
import yaml
import redis
import pickle
import psutil
from logging.handlers import TimedRotatingFileHandler

# Load config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Logging setup
timestamp = time.strftime(config["logging"]["filename_template"])
handler = TimedRotatingFileHandler(
    timestamp,
    when=config["logging"]["rotation_when"],
    interval=config["logging"]["rotation_interval"],
    backupCount=config["logging"]["rotation_backup_count"]
)
logging.basicConfig(
    level=getattr(logging, config["logging"]["level"]),
    format="%(asctime)s [%(levelname)s] - %(message)s",
    handlers=[handler, logging.StreamHandler()]
)

redis_client = redis.Redis(
    host=config["redis"]["host"],
    port=config["redis"]["port"],
    db=config["redis"]["db"],
    password=config["redis"]["password"]
)

class MonitoringOperations:
    def __init__(self):
        self._state_lock = threading.Lock()
        self.update_interval = config.get("monitoring", {}).get("update_interval", 1.0)  # Default 1 second
        self.state = {
            "cpu_percent": 0.0,
            "mem_percent": 0.0,
            "temperature": None
        }
        logging.debug("MonitoringOperations initialized with state")

    def get_system_stats(self):
        """Fetch system stats (CPU, memory, temperature)."""
        logging.debug("Fetching system stats")
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
                    logging.debug("No temperature sensor data available")
                else:
                    logging.debug(f"Temperature: {temperature}°C")
            except (AttributeError, NotImplementedError):
                logging.warning("Temperature monitoring not supported on this platform")
            return cpu_percent, mem_percent, temperature
        except Exception as e:
            logging.error(f"Error fetching system stats: {e}")
            return 0.0, 0.0, None

    def update_stats_redis(self):
        """Update metrics in Redis and local state."""
        with self._state_lock:
            try:
                self.state["cpu_percent"], self.state["mem_percent"], self.state["temperature"] = self.get_system_stats()
                redis_client.set("cpu_percent", str(self.state["cpu_percent"]))
                redis_client.set("mem_percent", str(self.state["mem_percent"]))
                redis_client.set("temperature", str(self.state["temperature"]) if self.state["temperature"] is not None else "null")
                stats_msg = pickle.dumps(self.state)
                redis_client.publish("system_stats_update", stats_msg)
                logging.debug(f"Updated Redis with stats: CPU={self.state['cpu_percent']}%, Mem={self.state['mem_percent']}%, Temp={self.state['temperature']}°C")
            except Exception as e:
                logging.error(f"Error updating Redis stats: {e}")

    async def broadcast_system_stats(self):
        """Background task to periodically update and broadcast stats."""
        logging.info("Starting system stats broadcast")
        while True:
            self.update_stats_redis()
            await asyncio.sleep(self.update_interval)