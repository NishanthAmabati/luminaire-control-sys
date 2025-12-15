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
                "current_intensity": 250,
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
            "last_state": {
                "auto_mode": False,
                "current_scene": None,
                "cw": 50.0,
                "ww": 50.0,
                "current_cct": 3500,
                "current_intensity": 250
            }
        }
        # Deep merge loaded_state with defaults, especially for nested scheduler object
        state = {**defaults, **loaded_state}
        # Ensure scheduler object has all required fields by merging with defaults
        if "scheduler" in state and isinstance(state["scheduler"], dict):
            state["scheduler"] = {**defaults["scheduler"], **state["scheduler"]}
        elif "scheduler" not in state or not isinstance(state["scheduler"], dict):
            # If scheduler is missing or invalid, use defaults
            state["scheduler"] = defaults["scheduler"]
        return state

    def _set_state(self, state):
        """
        Scheduler service owns system state and publishes to system_update channel.
        All data is JSON format.
        
        Timer service independently manages and broadcasts timer state.
        Scheduler service does not include timer data to avoid conflicts.
        """
        correlation_id = str(uuid.uuid4())
        with self._state_lock:
            # Ensure scene_data, cw, and ww are always present in the state
            if "scene_data" not in state:
                state["scene_data"] = {"cct": [], "intensity": []}
            if "cw" not in state:
                state["cw"] = 50.0
            if "ww" not in state:
                state["ww"] = 50.0
            
            # Write to new system_state key (JSON)
            redis_client.set("system_state", json.dumps(state))
            # Maintain legacy "state" key for backward compatibility
            redis_client.set("state", json.dumps(state))
            # Publish to system_update channel (JSON)
            # Timer data is NOT included - timer service handles its own broadcasting
            redis_client.publish("system_update", json.dumps(state))
            self.state = state
            try:
                # Also save to file as JSON
                # Timer data is NOT saved to file - timer service manages its own persistence
                with open(config["state"]["file"], "w") as f:
                    json.dump({
                        "auto_mode": state["auto_mode"],
                        "current_scene": state["current_scene"],
                        "cw": state["cw"],
                        "ww": state["ww"],
                        "current_cct": state["current_cct"],
                        "current_intensity": state["current_intensity"],
                        "isSystemOn": state["isSystemOn"]
                    }, f)
                logger.debug("State saved to file", correlation_id=correlation_id, file=config["state"]["file"])
            except Exception as e:
                logger.error("Failed to save state to file", correlation_id=correlation_id, file=config["state"]["file"], error=str(e))

    def log_basic(self, message: str):
        correlation_id = str(uuid.uuid4())
        timestamp = time.strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        # Only log to structured logger, NEVER publish to webapp
        logger.info("Basic Log", correlation_id=correlation_id, message=message)

    def log_advanced(self, message: str):
        correlation_id = str(uuid.uuid4())
        timestamp = time.strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        # Only log to structured logger, NEVER publish to webapp
        logger.debug("Advanced Log", correlation_id=correlation_id, message=message)

    async def run_smooth_scheduler(self, csv_path: str):
        correlation_id = str(uuid.uuid4())
        logger.debug("Starting scheduler", correlation_id=correlation_id, csv_path=csv_path)
        self.stop_event.clear()
        self.paused = False
        self.current_scheduler_task = asyncio.current_task()
        self.state["scheduler"]["status"] = "running"
        self._set_state(self.state)
        # Don't send log to webapp
        logger.info("Activated scene", correlation_id=correlation_id, scene=os.path.basename(csv_path))
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
                    logger.warning("Initial SendAll failed", correlation_id=correlation_id, error=resp.text)
                else:
                    logger.info("Applied initial scene values", correlation_id=correlation_id, cct=initial_cct, intensity=initial_intensity)

            last_interval_update = self.current_interval_index
            last_cw, last_ww, last_cct, last_intensity = cw, ww, initial_cct, initial_intensity
            update_interval = config.get("luminaire_operations", {}).get("scheduler_update_interval", 1.0)

            while not self.stop_event.is_set() and self.current_interval_index < 86400:
                loop_start = time.time()
                if self.paused:
                    logger.debug("Scheduler paused - sending manual mode values", correlation_id=correlation_id)
                    # When paused (manual mode), keep sending current manual control values every second
                    # This maintains continuous device updates as requested
                    # Manual controls set via webapp are stored in self.state and sent here
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(
                            f"http://{config['microservices']['luminaire_service']['host']}:{config['microservices']['luminaire_service']['port']}/sendAll",
                            json={"cw": self.state["cw"], "ww": self.state["ww"]}
                        )
                        if resp.status_code != 200:
                            logger.warning("SendAll failed in manual mode", correlation_id=correlation_id, error=resp.text)
                    
                    # Broadcast current state for webapp updates
                    self._set_state(self.state)
                    
                    # Sleep for update interval
                    await asyncio.sleep(update_interval)
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

                # Calculate new values with stabilization
                calc_cct = start_cct + (cct_diff * interval_progress)
                calc_intensity = start_intensity + (intensity_diff * interval_progress)
                
                # Round to 2 decimal places to prevent floating point drift
                calc_cct = round(calc_cct, 2)
                calc_intensity = round(calc_intensity, 2)
                
                # CRITICAL FIX: Clamp rate of change to prevent large oscillations
                # Max change per second: 10K CCT, 5 lux intensity
                # This prevents sudden jumps during scene transitions or system restarts
                max_cct_change_per_second = 10.0
                max_intensity_change_per_second = 5.0
                
                if last_cct is not None:
                    cct_delta = calc_cct - last_cct
                    if abs(cct_delta) > max_cct_change_per_second:
                        calc_cct = last_cct + (max_cct_change_per_second if cct_delta > 0 else -max_cct_change_per_second)
                        calc_cct = round(calc_cct, 2)
                
                if last_intensity is not None:
                    intensity_delta = calc_intensity - last_intensity
                    if abs(intensity_delta) > max_intensity_change_per_second:
                        calc_intensity = last_intensity + (max_intensity_change_per_second if intensity_delta > 0 else -max_intensity_change_per_second)
                        calc_intensity = round(calc_intensity, 2)
                
                self.state["current_cct"] = calc_cct
                self.state["current_intensity"] = calc_intensity
                
                # Update scheduler object with current values for consistency
                self.state["scheduler"]["current_cct"] = calc_cct
                self.state["scheduler"]["current_intensity"] = calc_intensity
                
                cw, ww = self.calculate_cw_ww_from_cct_intensity(calc_cct, calc_intensity)
                
                # Round cw/ww to 2 decimal places for stability
                cw = round(cw, 2)
                ww = round(ww, 2)
                
                self.state["cw"], self.state["ww"] = cw, ww
                # Calculate interval_progress as percentage (0-100) of day completion
                self.state["scheduler"]["interval_progress"] = round((current_idx / 86400) * 100, 2)
                self.state["scheduler"]["current_interval"] = current_idx // 10
                
                # Ensure all scheduler data is included in state before broadcasting
                # This includes interval_progress, current_interval, total_intervals, status
                logger.debug("State update before broadcast", correlation_id=correlation_id,
                           interval_progress=self.state["scheduler"]["interval_progress"],
                           current_interval=self.state["scheduler"]["current_interval"])
                
                self._set_state(self.state)

                # Threshold checks used only for conditional logging (not for device updates)
                # Device updates are now sent every second regardless of value changes
                cw_threshold = 0.1  # 0.1% change threshold
                ww_threshold = 0.1
                cct_threshold = 1.0  # 1K change threshold
                intensity_threshold = 1.0  # 1 lux change threshold
                
                cw_changed = abs(cw - last_cw) >= cw_threshold
                ww_changed = abs(ww - last_ww) >= ww_threshold
                cct_changed = abs(calc_cct - last_cct) >= cct_threshold
                intensity_changed = abs(calc_intensity - last_intensity) >= intensity_threshold
                
                values_changed = cw_changed or ww_changed
                should_log_info = (
                    values_changed or
                    cct_changed or intensity_changed or
                    current_idx // 10 != last_interval_update // 10
                )

                if should_log_info:
                    logger.info(
                        "Interval update",
                        correlation_id=correlation_id,
                        index=current_idx,
                        interval=current_interval,
                        progress=interval_progress,
                        cct=calc_cct,
                        intensity=calc_intensity,
                        cw=cw,
                        ww=ww,
                        sent_to_devices=True
                    )
                    last_interval_update = current_idx
                
                # Send to devices every update cycle (once per second, no threshold check)
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        f"http://{config['microservices']['luminaire_service']['host']}:{config['microservices']['luminaire_service']['port']}/sendAll",
                        json={"cw": cw, "ww": ww}
                    )
                    if resp.status_code != 200:
                        logger.warning("SendAll failed", correlation_id=correlation_id, error=resp.text)
                    else:
                        # Update last sent values only on successful send
                        last_cw, last_ww, last_cct, last_intensity = cw, ww, calc_cct, calc_intensity

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
        logger.info("Setting mode", correlation_id=correlation_id, auto=data.auto, current_scheduler_status=self.state["scheduler"]["status"])
        
        if not data.auto:
            # Switching to manual mode
            # Pause the scheduler but don't stop it
            if self.state["scheduler"]["status"] == "running":
                self.paused = True
                self.state["scheduler"]["status"] = "paused"
                logger.info("Scheduler paused for manual mode", correlation_id=correlation_id)
            
            # Restore last manual values if they exist (from previous manual mode session)
            # This preserves manual controls when switching back to manual mode
            if "last_state" in self.state and self.state["last_state"].get("auto_mode") == False:
                # Use last manual values from previous manual mode session
                last = self.state["last_state"]
                self.state["cw"] = last.get("cw", self.state["cw"])
                self.state["ww"] = last.get("ww", self.state["ww"])
                self.state["current_cct"] = last.get("current_cct", self.state["current_cct"])
                self.state["current_intensity"] = last.get("current_intensity", self.state["current_intensity"])
                logger.info("Restored manual mode values from last session", correlation_id=correlation_id, cw=self.state["cw"], ww=self.state["ww"])
            
            # Save current values as the new manual mode state
            self.state["last_state"] = {
                "auto_mode": False,
                "current_scene": self.state.get("current_scene"),
                "cw": self.state.get("cw", 50.0),
                "ww": self.state.get("ww", 50.0),
                "current_cct": self.state.get("current_cct", 3500),
                "current_intensity": self.state.get("current_intensity", 250)
            }
            
            self.state["auto_mode"] = False
            
        else:
            # Switching to auto mode
            self.stop_event.clear()
            self.state["auto_mode"] = True
            
            # If there's a current scene, reactivate it
            if self.state["current_scene"]:
                if self.state["current_scene"] in scene_data:
                    self.state["scene_data"] = scene_data[self.state["current_scene"]]
                    self.state["activationTime"] = time.strftime("%H:%M:%S")
                    self.state["loaded_scene"] = self.state["current_scene"]
                    
                    # If scheduler was paused, resume it
                    if self.state["scheduler"]["status"] == "paused" and self.current_scheduler_task:
                        self.paused = False
                        self.state["scheduler"]["status"] = "running"
                        logger.info("Scheduler resumed for auto mode", correlation_id=correlation_id, scene=self.state["current_scene"])
                    # If no scheduler running, start a new one
                    elif self.state["scheduler"]["status"] != "running":
                        self.state["scheduler"]["status"] = "running"
                        asyncio.create_task(self.run_smooth_scheduler(os.path.join(config["luminaire_operations"]["scene_directory"], self.state["current_scene"])))
                        logger.info("Scene reactivated for auto mode", correlation_id=correlation_id, scene=self.state["current_scene"])
                else:
                    logger.warning("Failed to reactivate scene", correlation_id=correlation_id, scene=self.state["current_scene"])
                    self.state["current_scene"] = None
                    self.state["scene_data"] = {"cct": [], "intensity": []}
                    self.state["scheduler"]["status"] = "idle"
            else:
                logger.info("No scene to activate in auto mode", correlation_id=correlation_id)
                self.state["scheduler"]["status"] = "idle"
        
        self._set_state(self.state)
        return self.state

    async def load_scene(self, data: LoadSceneData):
        correlation_id = str(uuid.uuid4())
        logger.info("Loading scene", correlation_id=correlation_id, scene=data.scene)
        self.state["loaded_scene"] = data.scene
        if data.scene in scene_data:
            self.state["scene_data"] = scene_data[data.scene]
            # Validate scene data arrays
            cct_array = self.state["scene_data"].get("cct", [])
            intensity_array = self.state["scene_data"].get("intensity", [])
            logger.info("Scene loaded", correlation_id=correlation_id, scene=data.scene,
                       cct_points=len(cct_array), intensity_points=len(intensity_array))
        else:
            logger.warning("Scene not found in scene_data", correlation_id=correlation_id, scene=data.scene)
            self.state["scene_data"] = {"cct": [], "intensity": []}
        self.log_basic(f"Loaded scene: {data.scene}")
        self._set_state(self.state)
        return self.state

    async def activate_scene(self, data: ActivateSceneData):
        correlation_id = str(uuid.uuid4())
        logger.info("Activating scene", correlation_id=correlation_id, scene=data.scene, current_auto_mode=self.state["auto_mode"])
        
        # Stop any currently running scheduler
        if self.state["scheduler"]["status"] == "running" and self.state["current_scene"]:
            self.stop_scheduler()
            await asyncio.sleep(0.1)
            logger.info("Stopped running scene before activation", correlation_id=correlation_id, previous_scene=self.state["current_scene"])
        
        # Update scene references
        self.state["current_scene"] = data.scene
        self.state["loaded_scene"] = data.scene
        
        # Load scene_data BEFORE broadcasting state
        # Add validation and fallback handling for missing scene_data
        if data.scene in scene_data:
            self.state["scene_data"] = scene_data[data.scene]
            # Validate that scene_data contains the required arrays with data
            cct_array = self.state["scene_data"].get("cct", [])
            intensity_array = self.state["scene_data"].get("intensity", [])
            logger.info("Scene data loaded", correlation_id=correlation_id, scene=data.scene, 
                       cct_points=len(cct_array), intensity_points=len(intensity_array))
        else:
            # Fallback to empty scene_data if scene not found
            self.state["scene_data"] = {"cct": [], "intensity": []}
            logger.warning("Scene not found, using empty scene_data", correlation_id=correlation_id, scene=data.scene)
        
        # Activate scene if in auto mode and scene exists
        if self.state["auto_mode"] and data.scene in scene_data:
            self.state["activationTime"] = time.strftime("%H:%M:%S")
            self.state["scheduler"]["status"] = "running"
            
            # Start the scheduler
            asyncio.create_task(self.run_smooth_scheduler(os.path.join(config["luminaire_operations"]["scene_directory"], data.scene)))
            self.log_basic(f"Activated scene: {data.scene} in auto mode")
            logger.info("Scene scheduler started", correlation_id=correlation_id, scene=data.scene)
        else:
            # Not in auto mode or scene not found
            if not self.state["auto_mode"]:
                logger.info("Scene loaded but not activated (manual mode)", correlation_id=correlation_id, scene=data.scene)
                self.log_basic(f"Scene loaded: {data.scene} (switch to Auto mode to activate)")
            else:
                logger.warning("Scene not found in scene_data", correlation_id=correlation_id, scene=data.scene)
                self.log_basic(f"Scene {data.scene} not found")
        
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
            # Save current state before turning off
            self.state["last_state"] = {
                "auto_mode": self.state["auto_mode"],
                "current_scene": self.state["current_scene"],
                "cw": self.state["cw"],
                "ww": self.state["ww"],
                "current_cct": self.state["current_cct"],
                "current_intensity": self.state["current_intensity"]
            }
            # Stop scheduler if running
            if self.state["scheduler"]["status"] == "running":
                self.stop_scheduler()
                logger.info("Scheduler stopped for system OFF", correlation_id=correlation_id)
            
            # Turn off lights
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
            # Restore previous state
            last_state = self.state.get("last_state", {})
            self.state["auto_mode"] = last_state.get("auto_mode", False)
            self.state["current_scene"] = last_state.get("current_scene", None)
            self.state["cw"] = last_state.get("cw", 50.0)
            self.state["ww"] = last_state.get("ww", 50.0)
            self.state["current_cct"] = last_state.get("current_cct", 3500)
            self.state["current_intensity"] = last_state.get("current_intensity", 250)
            
            # If auto mode was active with a scene, restart the scheduler
            if self.state["auto_mode"] and self.state["current_scene"] in scene_data:
                self.state["scene_data"] = scene_data[self.state["current_scene"]]
                self.state["activationTime"] = time.strftime("%H:%M:%S")
                self.state["loaded_scene"] = self.state["current_scene"]
                self.state["scheduler"]["status"] = "running"
                
                # Start scheduler - it will pick up from current time of day
                asyncio.create_task(self.run_smooth_scheduler(os.path.join(config["luminaire_operations"]["scene_directory"], self.state["current_scene"])))
                self.log_basic(f"Reactivated scene: {self.state['current_scene']} after system ON")
                logger.info("Scheduler restarted for system ON", correlation_id=correlation_id, scene=self.state["current_scene"])
            else:
                # Manual mode - just restore light levels
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        f"http://{config['microservices']['luminaire_service']['host']}:{config['microservices']['luminaire_service']['port']}/sendAll",
                        json={"cw": self.state["cw"], "ww": self.state["ww"]}
                    )
                    if resp.status_code != 200:
                        self.log_advanced(f"Toggle system ON failed: {resp.text}")
                        logger.warning("Toggle system ON failed", correlation_id=correlation_id, error=resp.text)
                logger.info("System turned ON in manual mode", correlation_id=correlation_id)
        
        self.state["isSystemOn"] = data.isSystemOn
        self.log_basic(f"System turned {'ON' if data.isSystemOn else 'OFF'}")
        self._set_state(self.state)
        return self.state