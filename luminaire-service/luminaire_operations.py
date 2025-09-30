import asyncio
import threading
import logging
import time
import re
import socket
import yaml
import pickle
import redis
from collections import deque
from functools import lru_cache
import psutil
from .models import SendData, SendAllData, AdjustData

# Load config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Logging setup
timestamp = time.strftime(config["logging"]["filename_template"])
from logging.handlers import TimedRotatingFileHandler
handler = TimedRotatingFileHandler(
    timestamp,
    when=config["logging"]["rotation_when"],
    interval=config["logging"]["rotation_interval"],
    backupCount=config["logging"]["rotation_backup_count"]
)
logging.basicConfig(
    level=getattr(logging, config["logging"]["level"]),
    format="%(asctime)s [%(levelname)s] - %(message)s",
    handlers=[handler]
)

redis_client = redis.Redis(
    host=config["redis"]["host"],
    port=config["redis"]["port"],
    db=config["redis"]["db"],
    password=config["redis"]["password"]
)

class LuminaireOperations:
    __slots__ = (
        '_devices_lock', '_state_lock', '_send_lock', 'min_cct', 'max_cct',
        'min_intensity', 'max_intensity', 'INACTIVITY_THRESHOLD', 'devices',
        'current_interval_index', 'total_intervals', 'start_time', 'stop_event',
        'paused', 'current_scheduler_task'
    )

    def __init__(self):
        self._devices_lock = threading.RLock()
        self._state_lock = threading.Lock()
        self._send_lock = threading.Lock()
        self.min_cct = config["luminaire_operations"]["min_cct"]
        self.max_cct = config["luminaire_operations"]["max_cct"]
        self.min_intensity = config["luminaire_operations"]["min_intensity"]
        self.max_intensity = config["luminaire_operations"]["max_intensity"]
        self.INACTIVITY_THRESHOLD = config["luminaire_operations"]["inactivity_threshold"]
        self.devices = {}
        self.current_interval_index = 0
        self.total_intervals = 0
        self.start_time = None
        self.stop_event = threading.Event()
        self.paused = False
        self.current_scheduler_task = None
        logging.debug("LuminaireOperations initialized")

    def stop_scheduler(self):
        """Stop the current scheduler task and reset state."""
        self.stop_event.set()
        if self.current_scheduler_task is not None:
            self.current_scheduler_task.cancel()
            self.current_scheduler_task = None
            logging.debug("Current scheduler task canceled")
        with self._state_lock:
            state = self._get_state()
            state["scene_data"] = {"cct": [], "intensity": []}
            state["current_scene"] = None
            state["loaded_scene"] = None
            state["scheduler"]["status"] = "idle"
            self._set_state(state)
        self.log_basic("Scheduler stopped")
        logging.debug("Scheduler stopped and state reset")

    def get_system_stats(self):
        logging.debug("Fetching system stats")
        cpu_percent, mem_percent = psutil.cpu_percent(interval=None), psutil.virtual_memory().percent
        # Fetch temperature data
        temperature = None
        try:
            temps = psutil.sensors_temperatures()
            # Look for common temperature sensors (e.g., 'coretemp' for Intel CPUs, 'k10temp' for AMD)
            for sensor in ['coretemp', 'k10temp', 'cpu_thermal']:
                if sensor in temps and temps[sensor]:
                    # Use the first available reading (highest priority)
                    temperature = temps[sensor][0].current
                    break
            if temperature is None:
                logging.debug("No temperature sensor data available")
            else:
                logging.debug(f"Temperature: {temperature}°C")
        except (AttributeError, NotImplementedError):
            logging.warning("Temperature monitoring not supported on this platform")
        logging.debug(f"System stats - CPU: {cpu_percent}%, Mem: {mem_percent}%, Temp: {temperature}°C")
        return cpu_percent, mem_percent, temperature

    def add(self, ip: str, writer):
        with self._devices_lock:
            self.devices[ip] = {"writer": writer, "last_seen": time.time(), "cw": 50.0, "ww": 50.0}
            state = self._get_state()
            if ip not in state["connected_devices"]:
                state["connected_devices"][ip] = {"cw": 50.0, "ww": 50.0}
            self._set_state(state)
            self.log_advanced(f"Luminaire connected: {ip}")
            logging.info(f"Added luminaire {ip}")
            logging.debug(f"Device list updated: {list(self.devices.keys())}")

    def disconnect(self, ip: str):
        with self._devices_lock:
            if ip in self.devices:
                writer = self.devices[ip].get("writer")
                if writer:
                    writer.close()
                del self.devices[ip]
                state = self._get_state()
                if ip in state["connected_devices"]:
                    del state["connected_devices"][ip]
                self._set_state(state)
                self.log_advanced(f"Luminaire disconnected: {ip}")
            logging.info(f"Disconnected {ip}")
            logging.debug(f"Device list after disconnect: {list(self.devices.keys())}")

    def clearALL(self):
        with self._devices_lock:
            for ip in list(self.devices.keys()):
                self.disconnect(ip)
            state = self._get_state()
            state["connected_devices"] = {}
            self._set_state(state)
        self.log_advanced("All luminaires disconnected.")
        logging.info("All luminaires disconnected.")
        logging.debug("Device list cleared")

    def processACK(self, ip: str, response: str) -> bool:
        logging.debug(f"Processing ACK from {ip}: {response}")
        try:
            if isinstance(response, bytes):
                response = response.decode('utf-8', errors='ignore')
            match = re.match(r"\*001(\d{3})(\d{3})ACK(\d{3})(\d{3})#", response)
            if not match:
                logging.warning(f"Invalid ACK format from {ip}: {response}")
                return False
            cw_raw, ww_raw = match.group(3), match.group(4)
            cw, ww = int(cw_raw) / 10, int(ww_raw) / 10
            with self._devices_lock:
                if ip in self.devices:
                    self.update_cw_ww_intensity(ip, cw, ww)  # Updates devices[ip] and state["connected_devices"]
                    self.log_advanced(f"Received [{ip}]: {response}")
                    logging.debug(f"Updated device {ip} - CW: {cw}%, WW: {ww}%")
                    return True
            return False
        except Exception as e:
            self.log_advanced(f"Error processing ACK for {ip}: {e}")
            logging.error(f"Error processing ACK for {ip}: {e}", exc_info=True)
            return False

    def log_basic(self, message: str):
        timestamp = time.strftime("%H:%M:%S")
        state = self._get_state()
        state["basicLogs"].append(f"[{timestamp}] {message}")
        self._set_state(state)
        redis_client.publish("log_update", pickle.dumps({
            "basicLogs": list(state["basicLogs"]),
            "advancedLogs": list(state["advancedLogs"])
        }))  # Publish log update
        logging.info(f"Basic Log: {message}")

    def log_advanced(self, message: str):
        timestamp = time.strftime("%H:%M:%S")
        state = self._get_state()
        state["advancedLogs"].append(f"[{timestamp}] {message}")
        self._set_state(state)
        redis_client.publish("log_update", pickle.dumps({
            "basicLogs": list(state["basicLogs"]),
            "advancedLogs": list(state["advancedLogs"])
        }))  # Publish log update
        logging.debug(f"Advanced Log: {message}")

    def list(self) -> dict:
        logging.debug("Listing connected devices")
        with self._devices_lock:
            now = time.time()
            devices = {ip: {"cw": data.get("cw"), "ww": data.get("ww")} for ip, data in self.devices.items() if now - data["last_seen"] < self.INACTIVITY_THRESHOLD}
            logging.debug(f"Active devices: {list(devices.keys())}")
            return devices

    def update_cw_ww_intensity(self, ip: str, cw: float, ww: float):
        with self._devices_lock:
            if ip in self.devices:
                self.devices[ip].update({"cw": cw, "ww": ww, "last_seen": time.time()})
                state = self._get_state()
                state["connected_devices"][ip] = {"cw": cw, "ww": ww}
                self._set_state(state)
                logging.debug(f"Updated {ip} - CW: {cw}%, WW: {ww}%")

    async def send(self, ip: str, cw: float, ww: float) -> bool:
        logging.debug(f"Sending to {ip} - CW: {cw}%, WW: {ww}%")
        retries = 0
        with self._devices_lock:
            if ip not in self.devices:
                logging.warning(f"Device {ip} not found for sending")
                return False
            writer = self.devices[ip]["writer"]
        while retries < config["luminaire_operations"]["max_retries"]:
            try:
                command = self.buildCommand(ip, cw, ww)
                writer.write(command.encode())
                await writer.drain()
                self.log_advanced(f"Sent [{ip}]: {command}")
                logging.debug(f"Successfully sent to {ip}")
                return True
            except (ConnectionError, OSError) as e:
                retries += 1
                self.log_advanced(f"Error sending to {ip} (retry {retries}/{config['luminaire_operations']['max_retries']}): {e}")
                logging.warning(f"Error sending to {ip} (retry {retries}/{config['luminaire_operations']['max_retries']}): {e}")
                if retries >= config["luminaire_operations"]["max_retries"]:
                    self.disconnect(ip)
            except Exception as e:
                retries += 1
                self.log_advanced(f"Unexpected error sending to {ip} (retry {retries}/{config['luminaire_operations']['max_retries']}): {e}")
                logging.warning(f"Unexpected error sending to {ip} (retry {retries}/{config['luminaire_operations']['max_retries']}): {e}")
                if retries >= config["luminaire_operations"]["max_retries"]:
                    self.disconnect(ip)
            await asyncio.sleep(0.5)
        logging.error(f"Failed to send to {ip} after {config['luminaire_operations']['max_retries']} retries")
        return False

    async def sendAll(self, cw: float, ww: float) -> tuple[bool, list]:
        logging.debug(f"Sending to all devices - CW: {cw}%, WW: {ww}%")
        failed_ips = []
        tasks = []
        with self._devices_lock:
            if not self.devices:
                logging.warning("No devices available to send to")
                return False, []
            for ip, device in list(self.devices.items()):
                command = self.buildCommand(ip, cw, ww)
                tasks.append(self.async_send(ip, device["writer"], command))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for ip, result in zip(list(self.devices.keys()), results):
            if isinstance(result, Exception):
                failed_ips.append(ip)
                self.log_advanced(f"Error sending to {ip}: {result}")
                logging.warning(f"Error sending to {ip}: {result}")
        success = len(failed_ips) == 0
        if not success:
            self.log_advanced(f"Failed to send to luminaires: {', '.join(failed_ips)}")
        state = self._get_state()
        state["current_cct"] = self.calculate_cct_from_cw_ww(cw, ww)
        self._set_state(state)
        logging.debug(f"SendAll completed - Success: {success}, Failed IPs: {failed_ips}")
        return success, failed_ips

    async def async_send(self, ip: str, writer, command: str) -> None:
        try:
            writer.write(command.encode())
            await writer.drain()
            self.log_advanced(f"Sent [{ip}]: {command}")
            logging.debug(f"Successfully sent to {ip}")
        except Exception as e:
            self.log_advanced(f"Error sending to {ip}: {e}")
            logging.warning(f"Error sending to {ip}: {e}")
            raise

    @lru_cache(maxsize=1024)
    def calculate_cw_ww_from_cct_intensity(self, cct: float, intensity: float) -> tuple[float, float]:
        logging.debug(f"Calculating CW/WW from CCT: {cct}, Intensity: {intensity}")
        cct = max(self.min_cct, min(self.max_cct, cct))
        intensity = max(self.min_intensity, min(self.max_intensity, intensity))
        intensity_percent = intensity / self.max_intensity
        cw_base = (cct - self.min_cct) / ((self.max_cct - self.min_cct) / 100.0)
        ww_base = 100.0 - cw_base
        cw = max(0.0, min(99.99, cw_base * intensity_percent))
        ww = max(0.0, min(99.99, ww_base * intensity_percent))
        logging.debug(f"Calculated - CW: {cw}%, WW: {ww}%")
        return cw, ww

    @lru_cache(maxsize=1024)
    def calculate_cct_from_cw_ww(self, cw: float, ww: float) -> float:
        logging.debug(f"Calculating CCT from CW: {cw}%, WW: {ww}%")
        total = cw + ww
        cct = 3500 if total == 0 else self.min_cct + ((cw / total) * 100 * ((self.max_cct - self.min_cct) / 100.0))
        logging.debug(f"Calculated CCT: {cct}K")
        return cct

    def buildCommand(self, ip: str, cw: float, ww: float) -> str:
        logging.debug(f"Building command for {ip} - CW: {cw}%, WW: {ww}%")
        try:
            ip_parts = ip.split(".")
            ip3, ip4 = f"{int(ip_parts[2]):03}", f"{int(ip_parts[3]):03}"
            command = f"*{ip3}{ip4}{int(cw*10):03}{int(ww*10):03}##"
            logging.debug(f"Built command: {command}")
            return command
        except (ValueError, IndexError) as e:
            self.log_advanced(f"Error building command for {ip}: {e}")
            logging.error(f"Error building command for {ip}: {e}", exc_info=True)
            raise ValueError(f"Invalid IP: {ip}")

    def _get_state(self):
        state_bytes = redis_client.get("state")
        if state_bytes:
            return pickle.loads(state_bytes)
        # Default state (from original)
        return {
            "auto_mode": False,
            "available_scenes": [],
            "current_scene": None,
            "loaded_scene": None,
            "cw": 50.0,
            "ww": 50.0,
            "scheduler": {
                "current_cct": 3500,
                "current_interval": 0,
                "total_intervals": config["luminaire_operations"]["total_intervals"],
                "status": "idle",
                "interval_progress": 0
            },
            "connected_devices": {},
            "basicLogs": deque(maxlen=config["luminaire_operations"]["log_basic_max_entries"]),
            "advancedLogs": deque(maxlen=config["luminaire_operations"]["log_advanced_max_entries"]),
            "scene_data": {"cct": [], "intensity": []},
            "current_cct": 3500,
            "current_intensity": 250,
            "is_manual_override": False,
            "cpu_percent": 0.0,
            "mem_percent": 0.0,
            "temperature": None,
            "activationTime": None,
            "isSystemOn": True,
            "last_state": {
                "auto_mode": False,
                "current_scene": None,
                "cw": 50.0,
                "ww": 50.0,
                "current_intensity": 250
            }
        }

    def _set_state(self, state):
        redis_client.set("state", pickle.dumps(state))
        redis_client.publish("state_update", pickle.dumps(state))  # Publish state update

    async def cleanup_stale_devices(self):
        while True:
            with self._devices_lock:
                now = time.time()
                stale_ips = [ip for ip, data in list(self.devices.items()) if now - data["last_seen"] > self.INACTIVITY_THRESHOLD]
                for ip in stale_ips:
                    self.disconnect(ip)
            await asyncio.sleep(config["luminaire_operations"]["cleanup_interval"])

    def pause_scheduler(self):
        self.paused = True
        self.log_basic("Scheduler paused")
        logging.info("Scheduler paused")

    def resume_scheduler(self):
        self.paused = False
        self.start_time = time.time() - (self.current_interval_index * config["luminaire_operations"]["scheduler_update_interval"])
        self.log_basic("Scheduler resumed")
        logging.info("Scheduler resumed")
        logging.debug(f"Resumed at index: {self.current_interval_index}, start_time: {self.start_time}")

    async def adjust_cw(self, data: AdjustData) -> bool:
        logging.debug(f"Adjusting CW by {data.delta} for IP: {data.ip}")
        if data.ip:
            with self._devices_lock:
                if data.ip not in self.devices or self.devices[data.ip].get("cw") is None:
                    logging.warning(f"Device {data.ip} not found or no CW data")
                    return False
                current_cw = self.devices[data.ip]["cw"]
                new_cw = max(0.0, min(100.0, current_cw + data.delta))
                self.log_basic(f"Adjusted CW to {new_cw}%")
                return await self.send(data.ip, new_cw, 100 - new_cw)
        else:
            with self._devices_lock:
                device_with_cw = next((ip for ip, data in self.devices.items() if data.get("cw") is not None), None)
                if not device_with_cw:
                    logging.warning("No device with CW data found")
                    return False
                current_cw = self.devices[device_with_cw]["cw"]
            new_cw = max(0.0, min(100.0, current_cw + data.delta))
            self.log_basic(f"Adjusted CW to {new_cw}%")
            success, _ = await self.sendAll(new_cw, 100 - new_cw)
            return success