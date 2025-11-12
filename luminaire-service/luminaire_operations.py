import asyncio
import threading
import logging
import time
import re
import socket
import yaml
import json
import pickle  # Temporary for backward compatibility during transition
import redis
import uuid
from collections import deque
from functools import lru_cache
import psutil
import structlog
from .models import SendData, SendAllData, AdjustData

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
logger = structlog.get_logger(service="luminaire-operations")

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
        'paused', 'current_scheduler_task', 'last_sent'
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
        self.last_sent = {}  # Track last sent cw/ww per device
        logger.debug("LuminaireOperations initialized")

    def stop_scheduler(self):
        """Stop the current scheduler task and reset state."""
        self.stop_event.set()
        if self.current_scheduler_task is not None:
            self.current_scheduler_task.cancel()
            self.current_scheduler_task = None
            logger.debug("Current scheduler task canceled")
        with self._state_lock:
            state = self._get_state()
            state["scene_data"] = {"cct": [], "intensity": []}
            state["current_scene"] = None
            state["loaded_scene"] = None
            state["scheduler"]["status"] = "idle"
            self._set_state(state)
        self.log_basic("Scheduler stopped")
        logger.debug("Scheduler stopped and state reset")

    def get_system_stats(self):
        logger.debug("Fetching system stats")
        cpu_percent, mem_percent = psutil.cpu_percent(interval=None), psutil.virtual_memory().percent
        temperature = None
        try:
            temps = psutil.sensors_temperatures()
            for sensor in ['coretemp', 'k10temp', 'cpu_thermal']:
                if sensor in temps and temps[sensor]:
                    temperature = temps[sensor][0].current
                    break
            if temperature is None:
                logger.debug("No temperature sensor data available")
            else:
                logger.debug(f"Temperature: {temperature}°C")
        except (AttributeError, NotImplementedError):
            logger.warning("Temperature monitoring not supported on this platform")
        logger.debug(f"System stats - CPU: {cpu_percent}%, Mem: {mem_percent}%, Temp: {temperature}°C")
        return cpu_percent, mem_percent, temperature

    def add(self, ip: str, writer):
        with self._devices_lock:
            self.devices[ip] = {"writer": writer, "last_seen": time.time(), "cw": 50.0, "ww": 50.0}
            # Write per-device state in JSON
            device_state = {
                "ip": ip,
                "cw": 50.0,
                "ww": 50.0,
                "last_seen": time.time(),
                "connected": True
            }
            redis_client.set(f"device_state:{ip}", json.dumps(device_state))
            # Publish device update
            redis_client.publish("device_update", json.dumps(device_state))
            self.log_basic(f"Luminaire connected: {ip}")
            logger.info("Added luminaire", device_id=ip)

    def disconnect(self, ip: str):
        with self._devices_lock:
            if ip in self.devices:
                writer = self.devices[ip].get("writer")
                if writer:
                    writer.close()
                # Get current device state before deletion
                current_cw = self.devices[ip].get("cw", 50.0)
                current_ww = self.devices[ip].get("ww", 50.0)
                del self.devices[ip]
                if ip in self.last_sent:
                    del self.last_sent[ip]
                # Update per-device state to disconnected
                device_state = {
                    "ip": ip,
                    "cw": current_cw,
                    "ww": current_ww,
                    "last_seen": time.time(),
                    "connected": False
                }
                redis_client.set(f"device_state:{ip}", json.dumps(device_state))
                # Publish device update
                redis_client.publish("device_update", json.dumps(device_state))
                self.log_basic(f"Luminaire disconnected: {ip}")
            logger.info("Disconnected", device_id=ip)

    def clearALL(self):
        with self._devices_lock:
            for ip in list(self.devices.keys()):
                self.disconnect(ip)
        self.log_basic("All luminaires disconnected.")
        logger.info("All luminaires disconnected.")

    def processACK(self, ip: str, response: str) -> bool:
        logger.debug(f"Processing ACK from {ip}", response=response)
        try:
            if isinstance(response, bytes):
                response = response.decode('utf-8', errors='ignore')
            match = re.match(r"\*001(\d{3})(\d{3})ACK(\d{3})(\d{3})#", response)
            if not match:
                logger.warning(f"Invalid ACK format from {ip}", response=response)
                return False
            cw_raw, ww_raw = match.group(3), match.group(4)
            cw, ww = int(cw_raw) / 10, int(ww_raw) / 10
            with self._devices_lock:
                if ip in self.devices:
                    # Update internal state
                    self.devices[ip].update({"cw": cw, "ww": ww, "last_seen": time.time()})
                    # Write per-device state in JSON
                    device_state = {
                        "ip": ip,
                        "cw": cw,
                        "ww": ww,
                        "last_seen": time.time(),
                        "connected": True
                    }
                    redis_client.set(f"device_state:{ip}", json.dumps(device_state))
                    # Publish device update event-driven
                    redis_client.publish("device_update", json.dumps(device_state))
                    self.log_basic(f"Received [{ip}]: {response}")
                    logger.debug(f"Updated device {ip}", cw=cw, ww=ww)
                    return True
            return False
        except Exception as e:
            self.log_basic(f"Error processing ACK for {ip}: {e}")
            logger.error(f"Error processing ACK for {ip}", error=str(e))
            return False

    def log_basic(self, message: str):
        correlation_id = str(uuid.uuid4())
        timestamp = time.strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        # Publish log event in JSON
        log_event = {
            "type": "basic",
            "timestamp": timestamp,
            "message": message,
            "formatted": formatted_message
        }
        redis_client.publish("log_update", json.dumps(log_event))
        logger.info("Basic Log", correlation_id=correlation_id, message=message)

    def log_advanced(self, message: str):
        correlation_id = str(uuid.uuid4())
        timestamp = time.strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        # Publish log event in JSON
        log_event = {
            "type": "advanced",
            "timestamp": timestamp,
            "message": message,
            "formatted": formatted_message
        }
        redis_client.publish("log_update", json.dumps(log_event))
        logger.debug("Advanced Log", correlation_id=correlation_id, message=message)

    def list(self) -> dict:
        logger.debug("Listing connected devices")
        with self._devices_lock:
            now = time.time()
            devices = {ip: {"cw": data.get("cw"), "ww": data.get("ww")} for ip, data in self.devices.items() if now - data["last_seen"] < self.INACTIVITY_THRESHOLD}
            logger.debug("Active devices", devices=list(devices.keys()))
            return devices

    def update_cw_ww_intensity(self, ip: str, cw: float, ww: float):
        with self._devices_lock:
            if ip in self.devices:
                self.devices[ip].update({"cw": cw, "ww": ww, "last_seen": time.time()})
                # Write per-device state in JSON
                device_state = {
                    "ip": ip,
                    "cw": cw,
                    "ww": ww,
                    "last_seen": time.time(),
                    "connected": True
                }
                redis_client.set(f"device_state:{ip}", json.dumps(device_state))
                # Note: Don't publish here, only on ACK or explicit events
                logger.debug(f"Updated {ip}", cw=cw, ww=ww)

    async def send(self, ip: str, cw: float, ww: float) -> bool:
        correlation_id = str(uuid.uuid4())
        logger.debug(f"Sending to {ip}", correlation_id=correlation_id, cw=cw, ww=ww)
        retries = 0
        with self._devices_lock:
            if ip not in self.devices:
                logger.warning(f"Device {ip} not found for sending", correlation_id=correlation_id)
                return False
            writer = self.devices[ip]["writer"]
        while retries < config["luminaire_operations"]["max_retries"]:
            try:
                command = self.buildCommand(ip, cw, ww)
                writer.write(command.encode())
                await writer.drain()
                # Log INFO only if cw/ww changed
                if ip not in self.last_sent or self.last_sent[ip] != (cw, ww):
                    self.log_basic(f"Sent [{ip}]: {command}")
                    logger.info(f"Sent to {ip}", correlation_id=correlation_id, command=command)
                    self.last_sent[ip] = (cw, ww)
                else:
                    logger.debug(f"Sent to {ip}", correlation_id=correlation_id, command=command)
                return True
            except (ConnectionError, OSError) as e:
                retries += 1
                self.log_basic(f"Error sending to {ip} (retry {retries}/{config['luminaire_operations']['max_retries']}): {e}")
                logger.warning(f"Error sending to {ip} (retry {retries}/{config['luminaire_operations']['max_retries']})", correlation_id=correlation_id, error=str(e))
                if retries >= config["luminaire_operations"]["max_retries"]:
                    self.disconnect(ip)
            except Exception as e:
                retries += 1
                self.log_basic(f"Unexpected error sending to {ip} (retry {retries}/{config['luminaire_operations']['max_retries']}): {e}")
                logger.warning(f"Unexpected error sending to {ip} (retry {retries}/{config['luminaire_operations']['max_retries']})", correlation_id=correlation_id, error=str(e))
                if retries >= config["luminaire_operations"]["max_retries"]:
                    self.disconnect(ip)
            await asyncio.sleep(0.5)
        logger.error(f"Failed to send to {ip} after {config['luminaire_operations']['max_retries']} retries", correlation_id=correlation_id)
        return False

    async def sendAll(self, cw: float, ww: float) -> tuple[bool, list]:
        correlation_id = str(uuid.uuid4())
        logger.debug(f"Sending to all devices", correlation_id=correlation_id, cw=cw, ww=ww)
        failed_ips = []
        tasks = []
        with self._devices_lock:
            if not self.devices:
                logger.warning("No devices available to send to", correlation_id=correlation_id)
                return False, []
            for ip, device in list(self.devices.items()):
                tasks.append(self.async_send(ip, device["writer"], cw, ww))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for ip, result in zip(list(self.devices.keys()), results):
            if isinstance(result, Exception):
                failed_ips.append(ip)
                self.log_basic(f"Error sending to {ip}: {result}")
                logger.warning(f"Error sending to {ip}", correlation_id=correlation_id, error=str(result))
        success = len(failed_ips) == 0
        if not success:
            self.log_basic(f"Failed to send to luminaires: {', '.join(failed_ips)}")
        state = self._get_state()
        state["current_cct"] = self.calculate_cct_from_cw_ww(cw, ww)
        self._set_state(state)
        logger.debug("SendAll completed", correlation_id=correlation_id, success=success, failed_ips=failed_ips)
        return success, failed_ips

    async def async_send(self, ip: str, writer, cw: float, ww: float) -> None:
        correlation_id = str(uuid.uuid4())
        try:
            command = self.buildCommand(ip, cw, ww)
            writer.write(command.encode())
            await writer.drain()
            # Log INFO only if cw/ww changed
            if ip not in self.last_sent or self.last_sent[ip] != (cw, ww):
                self.log_basic(f"Sent [{ip}]: {command}")
                logger.info(f"Sent to {ip}", correlation_id=correlation_id, command=command)
                self.last_sent[ip] = (cw, ww)
            else:
                logger.debug(f"Sent to {ip}", correlation_id=correlation_id, command=command)
        except Exception as e:
            self.log_basic(f"Error sending to {ip}: {e}")
            logger.warning(f"Error sending to {ip}", correlation_id=correlation_id, error=str(e))
            raise

    @lru_cache(maxsize=1024)
    def calculate_cw_ww_from_cct_intensity(self, cct: float, intensity: float) -> tuple[float, float]:
        logger.debug(f"Calculating CW/WW from CCT: {cct}, Intensity: {intensity}")
        cct = max(self.min_cct, min(self.max_cct, cct))
        intensity = max(self.min_intensity, min(self.max_intensity, intensity))
        intensity_percent = intensity / self.max_intensity
        cw_base = (cct - self.min_cct) / ((self.max_cct - self.min_cct) / 100.0)
        ww_base = 100.0 - cw_base
        cw = max(0.0, min(99.99, cw_base * intensity_percent))
        ww = max(0.0, min(99.99, ww_base * intensity_percent))
        logger.debug(f"Calculated", cw=cw, ww=ww)
        return cw, ww

    @lru_cache(maxsize=1024)
    def calculate_cct_from_cw_ww(self, cw: float, ww: float) -> float:
        logger.debug(f"Calculating CCT from CW: {cw}%, WW: {ww}%")
        total = cw + ww
        cct = 3500 if total == 0 else self.min_cct + ((cw / total) * 100 * ((self.max_cct - self.min_cct) / 100.0))
        logger.debug(f"Calculated CCT: {cct}K")
        return cct

    def buildCommand(self, ip: str, cw: float, ww: float) -> str:
        logger.debug(f"Building command for {ip}", cw=cw, ww=ww)
        try:
            ip_parts = ip.split(".")
            ip3, ip4 = f"{int(ip_parts[2]):03}", f"{int(ip_parts[3]):03}"
            command = f"*{ip3}{ip4}{int(cw*10):03}{int(ww*10):03}##"
            logger.debug(f"Built command", command=command)
            return command
        except (ValueError, IndexError) as e:
            self.log_basic(f"Error building command for {ip}: {e}")
            logger.error(f"Error building command for {ip}", error=str(e))
            raise ValueError(f"Invalid IP: {ip}")

    def _get_state(self):
        # Get system state from Redis (JSON format)
        # This is primarily used for scheduler-related operations
        # luminaire-service should minimize use of this global state
        state_bytes = redis_client.get("system_state")
        if state_bytes:
            try:
                return json.loads(state_bytes)
            except json.JSONDecodeError:
                # Fallback for legacy pickle format during transition
                try:
                    state_bytes = redis_client.get("state")
                    if state_bytes:
                        return pickle.loads(state_bytes)
                except:
                    pass
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
            "scene_data": {"cct": [], "intensity": []},
            "current_cct": 3500,
            "current_intensity": 250,
            "is_manual_override": False,
            "activationTime": None,
            "isSystemOn": True
        }

    def _set_state(self, state):
        # Set system state (owned by scheduler, but luminaire-service needs to update for scheduler operations)
        # Write in JSON format
        redis_client.set("system_state", json.dumps(state))
        # Also maintain legacy "state" key during transition
        redis_client.set("state", json.dumps(state))

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
        logger.info("Scheduler paused")

    def resume_scheduler(self):
        self.paused = False
        self.start_time = time.time() - (self.current_interval_index * config["luminaire_operations"]["scheduler_update_interval"])
        self.log_basic("Scheduler resumed")
        logger.info("Scheduler resumed")
        logger.debug(f"Resumed at index: {self.current_interval_index}, start_time: {self.start_time}")

    async def adjust_cw(self, data: AdjustData) -> bool:
        correlation_id = str(uuid.uuid4())
        logger.debug(f"Adjusting CW by {data.delta} for IP: {data.ip}", correlation_id=correlation_id)
        if data.ip:
            with self._devices_lock:
                if data.ip not in self.devices or self.devices[data.ip].get("cw") is None:
                    logger.warning(f"Device {data.ip} not found or no CW data", correlation_id=correlation_id)
                    return False
                current_cw = self.devices[data.ip]["cw"]
                new_cw = max(0.0, min(100.0, current_cw + data.delta))
                self.log_basic(f"Adjusted CW to {new_cw}%")
                return await self.send(data.ip, new_cw, 100 - new_cw)
        else:
            with self._devices_lock:
                device_with_cw = next((ip for ip, data in self.devices.items() if data.get("cw") is not None), None)
                if not device_with_cw:
                    logger.warning("No device with CW data found", correlation_id=correlation_id)
                    return False
                current_cw = self.devices[device_with_cw]["cw"]
            new_cw = max(0.0, min(100.0, current_cw + data.delta))
            self.log_basic(f"Adjusted CW to {new_cw}%")
            success, _ = await self.sendAll(new_cw, 100 - new_cw)
            return success