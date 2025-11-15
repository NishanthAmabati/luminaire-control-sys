import asyncio
import threading
import logging
import time
import datetime
import json
import redis
import csv
import os
from functools import lru_cache
from collections import deque
import yaml
import httpx
import structlog
import uuid
from scheduler_service.models import (
    SetModeData, LoadSceneData, ActivateSceneData, PauseResumeData,
    ManualOverrideData, AdjustLightData, SendAllData, SetCCTData,
    SetIntensityData, ToggleSystemData, SetTimerData, ToggleTimerData
)
from scheduler_service.scene_loader import scene_data

# Load config
with open("/app/config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Structured logging setup to STDOUT ONLY (no file handler)
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
logger = structlog.get_logger(service="scheduler-operations")

redis_client = redis.Redis(
    host=config["redis"]["host"],
    port=config["redis"]["port"],
    db=config["redis"]["db"],
    password=config["redis"]["password"],
    decode_responses=True
)

class SchedulerOperations:
    def __init__(self):
        self._state_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.paused = False
        self.current_scheduler_task = None
        self.current_interval_index = 0
        self.total_intervals = 0
        self.start_time = None
        self.min_cct = config["luminaire_operations"]["min_cct"]
        self.max_cct = config["luminaire_operations"]["max_cct"]
        self.min_intensity = config["luminaire_operations"]["min_intensity"]
        self.max_intensity = config["luminaire_operations"]["max_intensity"]
        self.state = self._get_state()
        self.last_sent = {}  # Track last sent cw/ww/cct/intensity
        logger.debug("SchedulerOperations initialized", correlation_id=str(uuid.uuid4()))

    def _get_state(self):
        # Try new system_state key first (JSON)
        state_bytes = redis_client.get("system_state")
        if not state_bytes:
            # Fallback to legacy "state" key
            state_bytes = redis_client.get("state")
        if state_bytes:
            try:
                loaded_state = json.loads(state_bytes)
            except json.JSONDecodeError:
                # If JSON fails, just use defaults
                loaded_state = {}
        else:
            loaded_state = {}
        defaults = {
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
            "isSystemOn": True,
            "system_timers": [],
            "isTimerEnabled": False,
            "last_state": {
                "auto_mode": False,
                "current_scene": None,
                "cw": 50.0,
                "ww": 50.0,
                "current_cct": 3500,
                "current_intensity": 250
            }
        }
        state = {**defaults, **loaded_state}
        return state

    def _set_state(self, state):
        """
        Scheduler service owns system state and publishes to system_update channel.
        All data is JSON format.
        """
        correlation_id = str(uuid.uuid4())
        with self._state_lock:
            # Write to new system_state key (JSON)
            redis_client.set("system_state", json.dumps(state))
            # Maintain legacy "state" key for backward compatibility
            redis_client.set("state", json.dumps(state))
            # Publish to system_update channel (JSON)
            redis_client.publish("system_update", json.dumps(state))
            self.state = state
            try:
                # Also save to file as JSON
                with open(config["state"]["file"], "w") as f:
                    json.dump({
                        "auto_mode": state["auto_mode"],
                        "current_scene": state["current_scene"],
                        "cw": state["cw"],
                        "ww": state["ww"],
                        "current_cct": state["current_cct"],
                        "current_intensity": state["current_intensity"],
                        "isSystemOn": state["isSystemOn"],
                        "system_timers": state["system_timers"],
                        "isTimerEnabled": state["isTimerEnabled"]
                    }, f)
                logger.debug("State saved to file", correlation_id=correlation_id, file=config["state"]["file"])
            except Exception as e:
                logger.error("Failed to save state to file", correlation_id=correlation_id, file=config["state"]["file"], error=str(e))

    def log_basic(self, message: str):
        correlation_id = str(uuid.uuid4())
        timestamp = time.strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        # Publish log event in JSON (no longer storing in state)
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
        # Publish log event in JSON (no longer storing in state)
        log_event = {
            "type": "advanced",
            "timestamp": timestamp,
            "message": message,
            "formatted": formatted_message
        }
        redis_client.publish("log_update", json.dumps(log_event))
        logger.debug("Advanced Log", correlation_id=correlation_id, message=message)

    async def run_smooth_scheduler(self, csv_path: str):
        correlation_id = str(uuid.uuid4())
        logger.debug("Starting scheduler", correlation_id=correlation_id, csv_path=csv_path)
        self.stop_event.clear()
        self.paused = False
        self.current_scheduler_task = asyncio.current_task()
        self.state["scheduler"]["status"] = "running"
        self._set_state(self.state)
        self.log_basic(f"Activated scene: {os.path.basename(csv_path)}")
        try:
            scene_name = os.path.basename(csv_path)
            if scene_name not in scene_data:
                raise FileNotFoundError(f"Scene {scene_name} not found in scene_data")
            
            with open(csv_path, newline='') as csvfile:
                reader = csv.reader(csvfile)
                next(reader)
                scene_data_list = [(int(row[0].split(':')[0]) * 60 + int(row[0].split(':')[1]), float(row[1]), float(row[2])) for row in reader]
            
            self.total_intervals = len(scene_data_list)
            self.state["scheduler"]["total_intervals"] = 8640
            self._set_state(self.state)

            start_time = datetime.datetime.now()
            seconds_since_midnight = (start_time.hour * 3600) + (start_time.minute * 60) + start_time.second
            self.current_interval_index = seconds_since_midnight
            self.start_time = time.time()
            logger.debug("Scheduler started", correlation_id=correlation_id, index=self.current_interval_index, start_time=self.start_time)

            current_idx = seconds_since_midnight
            current_interval = (current_idx // 1800) % self.total_intervals
            next_interval = (current_interval + 1) % self.total_intervals
            interval_progress = (current_idx % 1800) / 1799.0
            start_min, start_cct, start_intensity = scene_data_list[current_interval]
            end_min, end_cct, end_intensity = scene_data_list[next_interval]
            time_diff = ((end_min - start_min + 1440) % 1440) * 60
            cct_diff = end_cct - start_cct
            intensity_diff = end_intensity - start_intensity

            initial_cct = start_cct + (cct_diff * interval_progress)
            initial_intensity = start_intensity + (intensity_diff * interval_progress)
            cw, ww = self.calculate_cw_ww_from_cct_intensity(initial_cct, initial_intensity)
            self.state["current_cct"] = initial_cct
            self.state["current_intensity"] = initial_intensity
            self.state["cw"], self.state["ww"] = cw, ww
            self.state["scheduler"]["interval_progress"] = (current_idx / 86400) * 100
            self.state["scheduler"]["current_interval"] = current_idx // 10
            self._set_state(self.state)
            logger.info("Initial state set", correlation_id=correlation_id, cct=initial_cct, intensity=initial_intensity, cw=cw, ww=ww)

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"http://{config['microservices']['luminaire_service']['host']}:{config['microservices']['luminaire_service']['port']}/sendAll",
                    json={"cw": cw, "ww": ww}
                )
                if resp.status_code != 200:
                    self.log_advanced(f"Initial SendAll failed: {resp.text}")
                    logger.warning("Initial SendAll failed", correlation_id=correlation_id, error=resp.text)
                else:
                    self.log_basic(f"Applied initial scene values: CCT {initial_cct:.1f}K, Intensity {initial_intensity:.1f}lux")

            last_interval_update = self.current_interval_index
            last_cw, last_ww, last_cct, last_intensity = cw, ww, initial_cct, initial_intensity
            update_interval = config.get("luminaire_operations", {}).get("scheduler_update_interval", 1.0)

            while not self.stop_event.is_set() and self.current_interval_index < 86400:
                loop_start = time.time()
                if self.paused:
                    logger.debug("Scheduler paused", correlation_id=correlation_id)
                    await asyncio.sleep(0.1)
                    continue

                elapsed_time = time.time() - self.start_time
                current_idx = int(seconds_since_midnight + elapsed_time) % 86400
                self.current_interval_index = current_idx

                current_interval = (current_idx // 1800) % self.total_intervals
                next_interval = (current_interval + 1) % self.total_intervals
                interval_progress = (current_idx % 1800) / 1799.0

                start_min, start_cct, start_intensity = scene_data_list[current_interval]
                end_min, end_cct, end_intensity = scene_data_list[next_interval]
                time_diff = ((end_min - start_min + 1440) % 1440) * 60
                cct_diff = end_cct - start_cct
                intensity_diff = end_intensity - start_intensity

                self.state["current_cct"] = start_cct + (cct_diff * interval_progress)
                self.state["current_intensity"] = start_intensity + (intensity_diff * interval_progress)
                cw, ww = self.calculate_cw_ww_from_cct_intensity(self.state["current_cct"], self.state["current_intensity"])
                self.state["cw"], self.state["ww"] = cw, ww
                self.state["scheduler"]["interval_progress"] = (current_idx / 86400) * 100
                self.state["scheduler"]["current_interval"] = current_idx // 10
                self._set_state(self.state)

                should_log_info = (
                    cw != last_cw or ww != last_ww or
                    self.state["current_cct"] != last_cct or
                    self.state["current_intensity"] != last_intensity or
                    current_idx // 10 != last_interval_update // 10
                )

                if should_log_info:
                    logger.info(
                        "Interval update",
                        correlation_id=correlation_id,
                        index=current_idx,
                        interval=current_interval,
                        progress=interval_progress,
                        cct=self.state["current_cct"],
                        intensity=self.state["current_intensity"],
                        cw=cw,
                        ww=ww
                    )
                    last_interval_update = current_idx
                    last_cw, last_ww, last_cct, last_intensity = cw, ww, self.state["current_cct"], self.state["current_intensity"]

                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        f"http://{config['microservices']['luminaire_service']['host']}:{config['microservices']['luminaire_service']['port']}/sendAll",
                        json={"cw": cw, "ww": ww}
                    )
                    if resp.status_code != 200:
                        self.log_advanced(f"SendAll failed: {resp.text}")
                        logger.warning("SendAll failed", correlation_id=correlation_id, error=resp.text)

                logger.debug(
                    "Scheduler tick",
                    correlation_id=correlation_id,
                    index=current_idx,
                    interval=current_interval,
                    progress=interval_progress,
                    cct=self.state["current_cct"],
                    intensity=self.state["current_intensity"],
                    cw=cw,
                    ww=ww
                )

                elapsed = time.time() - loop_start
                sleep_time = max(0, update_interval - elapsed)
                await asyncio.sleep(sleep_time)

            if not self.stop_event.is_set():
                self.state["scheduler"]["status"] = "completed"
                self._set_state(self.state)
                self.log_basic(f"Scene completed: {os.path.basename(csv_path)}")
                logger.info("Scene execution completed", correlation_id=correlation_id)
        except FileNotFoundError:
            self.log_advanced(f"CSV file not found: {csv_path}")
            logger.error("CSV file not found", correlation_id=correlation_id, csv_path=csv_path)
            self.state["scheduler"]["status"] = "failed"
            self._set_state(self.state)
        except Exception as e:
            self.log_advanced(f"Error running scheduler: {e}")
            logger.error("Error running scheduler", correlation_id=correlation_id, error=str(e))
            self.state["scheduler"]["status"] = "failed"
            self._set_state(self.state)
        finally:
            logger.debug("Scheduler terminated", correlation_id=correlation_id, csv_path=csv_path)
            self.state["scheduler"]["status"] = "idle" if self.state["scheduler"]["status"] != "failed" else "failed"
            self._set_state(self.state)

    @lru_cache(maxsize=1024)
    def calculate_cw_ww_from_cct_intensity(self, cct: float, intensity: float) -> tuple[float, float]:
        correlation_id = str(uuid.uuid4())
        logger.debug("Calculating CW/WW", correlation_id=correlation_id, cct=cct, intensity=intensity)
        cct = max(self.min_cct, min(self.max_cct, cct))
        intensity = max(self.min_intensity, min(self.max_intensity, intensity))
        intensity_percent = intensity / self.max_intensity
        cw_base = (cct - self.min_cct) / ((self.max_cct - self.min_cct) / 100.0)
        ww_base = 100.0 - cw_base
        cw = max(0.0, min(99.99, cw_base * intensity_percent))
        ww = max(0.0, min(99.99, ww_base * intensity_percent))
        logger.debug("Calculated CW/WW", correlation_id=correlation_id, cw=cw, ww=ww)
        return cw, ww

    @lru_cache(maxsize=1024)
    def calculate_cct_from_cw_ww(self, cw: float, ww: float) -> float:
        correlation_id = str(uuid.uuid4())
        logger.debug("Calculating CCT", correlation_id=correlation_id, cw=cw, ww=ww)
        total = cw + ww
        cct = 3500 if total == 0 else self.min_cct + ((cw / total) * 100 * ((self.max_cct - self.min_cct) / 100.0))
        logger.debug("Calculated CCT", correlation_id=correlation_id, cct=cct)
        return cct

    def get_nearest_interval(self, current_time):
        correlation_id = str(uuid.uuid4())
        logger.debug("Getting nearest interval", correlation_id=correlation_id, current_time=current_time)
        seconds_since_midnight = (current_time.hour * 3600) + (current_time.minute * 60) + current_time.second
        logger.debug("Nearest interval calculated", correlation_id=correlation_id, seconds=seconds_since_midnight)
        return seconds_since_midnight

    async def set_mode(self, data: SetModeData):
        correlation_id = str(uuid.uuid4())
        logger.info("Setting mode", correlation_id=correlation_id, auto=data.auto)
        self.state["auto_mode"] = data.auto
        self.stop_event.set() if not data.auto else self.stop_event.clear()
        self.log_basic(f"Switched to {'Auto' if data.auto else 'Manual'} mode")
        if not data.auto:
            self.state["scene_data"] = {"cct": [], "intensity": []}
            self.state["loaded_scene"] = None
            self.state["scheduler"]["status"] = "idle"
        elif data.auto and self.state["current_scene"]:
            if self.state["current_scene"] in scene_data:
                self.state["scene_data"] = scene_data[self.state["current_scene"]]
                self.state["activationTime"] = time.strftime("%H:%M:%S")
                self.state["loaded_scene"] = self.state["current_scene"]
                self.state["scheduler"]["status"] = "running"
                asyncio.create_task(self.run_smooth_scheduler(os.path.join(config["luminaire_operations"]["scene_directory"], self.state["current_scene"])))
                self.log_basic(f"Reactivated scene: {self.state['current_scene']}")
            else:
                self.log_basic(f"Failed to reactivate scene {self.state['current_scene']}: not found")
                logger.warning("Failed to reactivate scene", correlation_id=correlation_id, scene=self.state["current_scene"])
                self.state["current_scene"] = None
                self.state["scene_data"] = {"cct": [], "intensity": []}
        self._set_state(self.state)
        return self.state

    async def load_scene(self, data: LoadSceneData):
        correlation_id = str(uuid.uuid4())
        logger.info("Loading scene", correlation_id=correlation_id, scene=data.scene)
        self.state["loaded_scene"] = data.scene
        if data.scene in scene_data:
            self.state["scene_data"] = scene_data[data.scene]
        self.log_basic(f"Loaded scene: {data.scene}")
        self._set_state(self.state)
        return self.state

    async def activate_scene(self, data: ActivateSceneData):
        correlation_id = str(uuid.uuid4())
        logger.info("Activating scene", correlation_id=correlation_id, scene=data.scene)
        if self.state["scheduler"]["status"] == "running" and self.state["current_scene"]:
            self.stop_scheduler()
            await asyncio.sleep(0.1)
            logger.debug("Stopped running scene", correlation_id=correlation_id, scene=self.state["current_scene"])
        self.state["current_scene"] = data.scene
        self.state["loaded_scene"] = data.scene
        if self.state["auto_mode"] and data.scene in scene_data:
            self.state["scene_data"] = scene_data[data.scene]
            self.state["activationTime"] = time.strftime("%H:%M:%S")
            self.state["scheduler"]["status"] = "running"
            asyncio.create_task(self.run_smooth_scheduler(os.path.join(config["luminaire_operations"]["scene_directory"], data.scene)))
        self.log_basic(f"Activated scene: {data.scene}")
        self._set_state(self.state)
        return self.state

    def stop_scheduler(self):
        correlation_id = str(uuid.uuid4())
        logger.info("Stopping scheduler", correlation_id=correlation_id)
        self.stop_event.set()
        if self.current_scheduler_task is not None:
            self.current_scheduler_task.cancel()
            self.current_scheduler_task = None
        self.state["scene_data"] = {"cct": [], "intensity": []}
        self.state["current_scene"] = None
        self.state["loaded_scene"] = None
        self.state["scheduler"]["status"] = "idle"
        self._set_state(self.state)
        self.log_basic("Scheduler stopped")
        logger.info("Scheduler stopped", correlation_id=correlation_id)

    async def manual_override(self, data: ManualOverrideData):
        correlation_id = str(uuid.uuid4())
        logger.info("Setting manual override", correlation_id=correlation_id, override=data.override)
        self.state["is_manual_override"] = data.override
        if not data.override and self.state["auto_mode"] and self.state["current_scene"]:
            self.start_time = None
            asyncio.create_task(self.run_smooth_scheduler(os.path.join(config["luminaire_operations"]["scene_directory"], self.state["current_scene"])))
        self.log_basic(f"Manual override {'enabled' if data.override else 'disabled'}")
        self._set_state(self.state)
        return self.state

    async def adjust_light(self, data: AdjustLightData):
        correlation_id = str(uuid.uuid4())
        logger.info("Adjusting light", correlation_id=correlation_id, light_type=data.light_type, delta=data.delta)
        if data.light_type == "cw":
            self.state["cw"] = min(100, max(0, (self.state["cw"] or 50) + data.delta))
            self.state["ww"] = 100 - self.state["cw"]
        elif data.light_type == "ww":
            self.state["ww"] = min(100, max(0, (self.state["ww"] or 50) + data.delta))
            self.state["cw"] = 100 - self.state["ww"]
        self.state["current_cct"] = self.calculate_cct_from_cw_ww(self.state["cw"], self.state["ww"])
        self.log_basic(f"Adjusted {data.light_type.upper()} by {data.delta}%")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"http://{config['microservices']['luminaire_service']['host']}:{config['microservices']['luminaire_service']['port']}/sendAll",
                json={"cw": self.state["cw"], "ww": self.state["ww"]}
            )
            if resp.status_code != 200:
                self.log_advanced(f"Adjust light failed: {resp.text}")
                logger.warning("Adjust light failed", correlation_id=correlation_id, error=resp.text)
        self._set_state(self.state)
        return self.state

    async def send_all(self, data: SendAllData):
        correlation_id = str(uuid.uuid4())
        logger.info("Sending to all", correlation_id=correlation_id, cw=data.cw, ww=data.ww, intensity=data.intensity)
        self.state["cw"], self.state["ww"], self.state["current_intensity"] = data.cw, data.ww, data.intensity
        self.state["current_cct"] = self.calculate_cct_from_cw_ww(data.cw, data.ww)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"http://{config['microservices']['luminaire_service']['host']}:{config['microservices']['luminaire_service']['port']}/sendAll",
                json={"cw": data.cw, "ww": data.ww}
            )
            if resp.status_code != 200:
                self.log_advanced(f"SendAll failed: {resp.text}")
                logger.warning("SendAll failed", correlation_id=correlation_id, error=resp.text)
        self.log_basic(f"Sent CW: {data.cw}%, WW: {data.ww}%, Intensity: {data.intensity}")
        self._set_state(self.state)
        return self.state

    async def set_cct(self, data: SetCCTData):
        correlation_id = str(uuid.uuid4())
        logger.info("Setting CCT", correlation_id=correlation_id, cct=data.cct)
        self.state["current_cct"] = data.cct
        cw, ww = self.calculate_cw_ww_from_cct_intensity(data.cct, self.state["current_intensity"])
        self.state["cw"], self.state["ww"] = cw, ww
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"http://{config['microservices']['luminaire_service']['host']}:{config['microservices']['luminaire_service']['port']}/sendAll",
                json={"cw": cw, "ww": ww}
            )
            if resp.status_code != 200:
                self.log_advanced(f"Set CCT failed: {resp.text}")
                logger.warning("Set CCT failed", correlation_id=correlation_id, error=resp.text)
        self.log_basic(f"Set CCT to {data.cct}K")
        self._set_state(self.state)
        return self.state

    async def set_intensity(self, data: SetIntensityData):
        correlation_id = str(uuid.uuid4())
        logger.info("Setting intensity", correlation_id=correlation_id, intensity=data.intensity)
        self.state["current_intensity"] = data.intensity
        cw, ww = self.calculate_cw_ww_from_cct_intensity(self.state["current_cct"], data.intensity)
        self.state["cw"], self.state["ww"] = cw, ww
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"http://{config['microservices']['luminaire_service']['host']}:{config['microservices']['luminaire_service']['port']}/sendAll",
                json={"cw": cw, "ww": ww}
            )
            if resp.status_code != 200:
                self.log_advanced(f"Set Intensity failed: {resp.text}")
                logger.warning("Set Intensity failed", correlation_id=correlation_id, error=resp.text)
        self.log_basic(f"Set Intensity to {data.intensity}Lux")
        self._set_state(self.state)
        return self.state

    async def toggle_system(self, data: ToggleSystemData):
        correlation_id = str(uuid.uuid4())
        logger.info("Toggling system", correlation_id=correlation_id, isSystemOn=data.isSystemOn)
        if not data.isSystemOn:
            self.state["last_state"] = {
                "auto_mode": self.state["auto_mode"],
                "current_scene": self.state["current_scene"],
                "cw": self.state["cw"],
                "ww": self.state["ww"],
                "current_cct": self.state["current_cct"],
                "current_intensity": self.state["current_intensity"]
            }
            self.stop_scheduler()
            self.state["cw"], self.state["ww"] = 0.0, 0.0
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"http://{config['microservices']['luminaire_service']['host']}:{config['microservices']['luminaire_service']['port']}/sendAll",
                    json={"cw": 0.0, "ww": 0.0}
                )
                if resp.status_code != 200:
                    self.log_advanced(f"Toggle system OFF failed: {resp.text}")
                    logger.warning("Toggle system OFF failed", correlation_id=correlation_id, error=resp.text)
        else:
            last_state = self.state.get("last_state", {})
            self.state["auto_mode"] = last_state.get("auto_mode", False)
            self.state["current_scene"] = last_state.get("current_scene", None)
            self.state["cw"] = last_state.get("cw", 50.0)
            self.state["ww"] = last_state.get("ww", 50.0)
            self.state["current_cct"] = last_state.get("current_cct", 3500)
            self.state["current_intensity"] = last_state.get("current_intensity", 250)
            if self.state["auto_mode"] and self.state["current_scene"] in scene_data:
                self.state["scene_data"] = scene_data[self.state["current_scene"]]
                self.state["activationTime"] = time.strftime("%H:%M:%S")
                self.state["loaded_scene"] = self.state["current_scene"]
                self.state["scheduler"]["status"] = "running"
                asyncio.create_task(self.run_smooth_scheduler(os.path.join(config["luminaire_operations"]["scene_directory"], self.state["current_scene"])))
                self.log_basic(f"Reactivated scene: {self.state['current_scene']}")
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"http://{config['microservices']['luminaire_service']['host']}:{config['microservices']['luminaire_service']['port']}/sendAll",
                    json={"cw": self.state["cw"], "ww": self.state["ww"]}
                )
                if resp.status_code != 200:
                    self.log_advanced(f"Toggle system ON failed: {resp.text}")
                    logger.warning("Toggle system ON failed", correlation_id=correlation_id, error=resp.text)
        self.state["isSystemOn"] = data.isSystemOn
        self.log_basic(f"System turned {'ON' if data.isSystemOn else 'OFF'}")
        self._set_state(self.state)
        return self.state

    async def set_timer(self, data: SetTimerData):
        correlation_id = str(uuid.uuid4())
        logger.info("Setting timers", correlation_id=correlation_id, timers=[timer.dict() for timer in data.timers])
        for timer in data.timers:
            try:
                datetime.datetime.strptime(timer.on, "%H:%M")
                datetime.datetime.strptime(timer.off, "%H:%M")
            except ValueError:
                self.log_advanced(f"Invalid timer format: {timer}")
                logger.error("Invalid timer format", correlation_id=correlation_id, timer=str(timer))
                return {"error": f"Invalid timer format: {timer}"}
        self.state["system_timers"] = [timer.dict() for timer in data.timers]
        self.state["isTimerEnabled"] = True if data.timers else False
        self._set_state(self.state)
        self.log_basic(f"Set {len(data.timers)} system timers")
        logger.info("Timers set", correlation_id=correlation_id, timer_count=len(data.timers))
        return self.state

    def reset_timers(self):
        correlation_id = str(uuid.uuid4())
        logger.info("Resetting timers", correlation_id=correlation_id)
        self.state["system_timers"] = []
        self.state["isTimerEnabled"] = False
        self._set_state(self.state)
        self.log_basic("Timers reset and disabled")
        logger.info("Timers reset", correlation_id=correlation_id)
        return self.state

    async def run_timer_scheduler(self):
        logging.debug("Starting timer scheduler")
        api_url = f"http://{config['server']['host']}:{config['microservices']['api_port']}"

        # To avoid retriggering within the same day, store last trigger per timer (by "on"/"off")
        if "timer_last_trigger" not in self.state:
            self.state["timer_last_trigger"] = {}

        while True:
            if not self.state.get("isTimerEnabled", False):
                logging.debug("Timer scheduler disabled, skipping checks")
                await asyncio.sleep(config["scheduler"]["timer_check_interval"])
                continue

            now = datetime.datetime.now()
            current_time_str = now.strftime("%H:%M")
            today_str = now.strftime("%Y-%m-%d")

            timers = self.state.get("system_timers", [])
            for idx, timer in enumerate(timers):
                timer_id_on = f"timer{idx}-on:{timer['on']}"
                timer_id_off = f"timer{idx}-off:{timer['off']}"
                last_trigger = self.state["timer_last_trigger"]

                # ON logic: Trigger if current time >= timer["on"], today not yet triggered, and system is OFF
                # (Allows triggering if service started late/loop missed the exact minute.)
                on_dt = now.replace(
                    hour=int(timer["on"].split(":")[0]),
                    minute=int(timer["on"].split(":")[1]),
                    second=0, microsecond=0
                )
                off_dt = now.replace(
                    hour=int(timer["off"].split(":")[0]),
                    minute=int(timer["off"].split(":")[1]),
                    second=0, microsecond=0
                )

                # ON Trigger - removed state condition to allow triggering regardless of current state
                if (
                    now >= on_dt
                    and last_trigger.get(timer_id_on) != today_str
                ):
                    try:
                        async with httpx.AsyncClient() as client:
                            resp = await client.post(f"{api_url}/api/toggle_system", json={"isSystemOn": True})
                            if resp.status_code == 200:
                                self.log_basic(f"Timer triggered: System turned ON at {timer['on']}")
                                last_trigger[timer_id_on] = today_str
                                # Persist trigger state to Redis immediately
                                await self.redis_client.hset("state", "timer_last_trigger", json.dumps(last_trigger))
                            else:
                                self.log_advanced(f"Timer ON failed at {timer['on']}: {resp.text}")
                    except Exception as e:
                        self.log_advanced(f"Timer ON error at {timer['on']}: {e}")
                        logging.error(f"Timer ON error at {timer['on']}: {e}")

                # OFF Trigger - removed state condition to allow triggering regardless of current state
                if (
                    now >= off_dt
                    and last_trigger.get(timer_id_off) != today_str
                ):
                    try:
                        async with httpx.AsyncClient() as client:
                            resp = await client.post(f"{api_url}/api/toggle_system", json={"isSystemOn": False})
                            if resp.status_code == 200:
                                self.log_basic(f"Timer triggered: System turned OFF at {timer['off']}")
                                last_trigger[timer_id_off] = today_str
                                # Persist trigger state to Redis immediately
                                await self.redis_client.hset("state", "timer_last_trigger", json.dumps(last_trigger))
                            else:
                                self.log_advanced(f"Timer OFF failed at {timer['off']}: {resp.text}")
                    except Exception as e:
                        self.log_advanced(f"Timer OFF error at {timer['off']}: {e}")
                        logging.error(f"Timer OFF error at {timer['off']}: {e}")

            # Persist the last-trigger dict
            self.state["timer_last_trigger"] = self.state.get("timer_last_trigger", {})
            self._set_state(self.state)
            await asyncio.sleep(config["scheduler"]["timer_check_interval"])