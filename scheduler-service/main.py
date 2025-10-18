import asyncio
import uvicorn
from fastapi import FastAPI
import yaml
import resource
import logging
import time
import uuid
import pickle
import redis
import structlog
from scheduler_service.scheduler_operations import SchedulerOperations
from scheduler_service.scene_loader import load_scenes
from scheduler_service.models import (
    SetModeData, LoadSceneData, ActivateSceneData, PauseResumeData,
    ManualOverrideData, AdjustLightData, SendAllData, SetCCTData,
    SetIntensityData, ToggleSystemData, SetTimerData, ToggleTimerData
)

# Load config
with open("/app/config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Structured logging setup
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
timestamp = time.strftime("%Y-%m-%d.log")
handler = logging.handlers.TimedRotatingFileHandler(
    f"/app/logs/{timestamp}",
    when=config["logging"]["rotation_when"],
    interval=config["logging"]["rotation_interval"],
    backupCount=config["logging"]["rotation_backup_count"]
)
logging.basicConfig(
    level=getattr(logging, config["logging"]["level"]),
    format="%(message)s",
    handlers=[handler, logging.StreamHandler()]
)
logger = structlog.get_logger(service="scheduler-service")

# Initialize Redis client
redis_client = redis.Redis(
    host=config["redis"]["host"],
    port=config["redis"]["port"],
    db=config["redis"]["db"],
    password=config["redis"]["password"],
    decode_responses=False
)

app = FastAPI(title="Scheduler Service", version="1.0.0")
ops = SchedulerOperations()

@app.get("/health")
async def health():
    correlation_id = str(uuid.uuid4())
    logger.info("Health check", correlation_id=correlation_id, endpoint="/health")
    return {"status": "healthy"}

@app.post("/set_mode")
async def api_set_mode(data: SetModeData):
    correlation_id = str(uuid.uuid4())
    logger.info("Setting mode", correlation_id=correlation_id, auto=data.auto)
    state = await ops.set_mode(data)
    logger.info("Mode set", correlation_id=correlation_id, auto=data.auto)
    return {"status": "success", "state": state}

@app.post("/load_scene")
async def api_load_scene(data: LoadSceneData):
    correlation_id = str(uuid.uuid4())
    logger.info("Loading scene", correlation_id=correlation_id, scene=data.scene)
    state = await ops.load_scene(data)
    logger.info("Scene loaded", correlation_id=correlation_id, scene=data.scene)
    return {"status": "success", "state": state}

@app.post("/activate_scene")
async def api_activate_scene(data: ActivateSceneData):
    correlation_id = str(uuid.uuid4())
    logger.info("Activating scene", correlation_id=correlation_id, scene=data.scene)
    state = await ops.activate_scene(data)
    logger.info("Scene activated", correlation_id=correlation_id, scene=data.scene)
    return {"status": "success", "state": state}

@app.post("/stop_scheduler")
async def api_stop_scheduler():
    correlation_id = str(uuid.uuid4())
    logger.info("Stopping scheduler", correlation_id=correlation_id)
    ops.stop_scheduler()
    logger.info("Scheduler stopped", correlation_id=correlation_id)
    return {"status": "stopped"}

@app.post("/pause_resume")
async def api_pause_resume(data: PauseResumeData):
    correlation_id = str(uuid.uuid4())
    if data.pause:
        logger.info("Pausing scheduler", correlation_id=correlation_id)
        ops.stop_scheduler()
        logger.info("Scheduler paused", correlation_id=correlation_id)
        return {"status": "paused"}
    else:
        state = ops._get_state()
        if state["current_scene"]:
            logger.info("Resuming scheduler", correlation_id=correlation_id, scene=state["current_scene"])
            await ops.activate_scene(ActivateSceneData(scene=state["current_scene"]))
            logger.info("Scheduler resumed", correlation_id=correlation_id, scene=state["current_scene"])
            return {"status": "resumed"}
        logger.warning("No scene to resume", correlation_id=correlation_id)
        return {"status": "no_scene_to_resume"}

@app.post("/manual_override")
async def api_manual_override(data: ManualOverrideData):
    correlation_id = str(uuid.uuid4())
    logger.info("Setting manual override", correlation_id=correlation_id, override=data.override)
    state = await ops.manual_override(data)
    logger.info("Manual override set", correlation_id=correlation_id, override=data.override)
    return {"status": "success", "state": state}

@app.post("/adjust_light")
async def api_adjust_light(data: AdjustLightData):
    correlation_id = str(uuid.uuid4())
    logger.info("Adjusting light", correlation_id=correlation_id, light_type=data.light_type, delta=data.delta)
    state = await ops.adjust_light(data)
    logger.info("Light adjusted", correlation_id=correlation_id, light_type=data.light_type, delta=data.delta)
    return {"status": "success", "state": state}

@app.post("/send_all")
async def api_send_all(data: SendAllData):
    correlation_id = str(uuid.uuid4())
    logger.info("Sending to all", correlation_id=correlation_id, cw=data.cw, ww=data.ww, intensity=data.intensity)
    state = await ops.send_all(data)
    logger.info("Sent to all", correlation_id=correlation_id, cw=data.cw, ww=data.ww, intensity=data.intensity)
    return {"status": "success", "state": state}

@app.post("/set_cct")
async def api_set_cct(data: SetCCTData):
    correlation_id = str(uuid.uuid4())
    logger.info("Setting CCT", correlation_id=correlation_id, cct=data.cct)
    state = await ops.set_cct(data)
    logger.info("CCT set", correlation_id=correlation_id, cct=data.cct)
    return {"status": "success", "state": state}

@app.post("/set_intensity")
async def api_set_intensity(data: SetIntensityData):
    correlation_id = str(uuid.uuid4())
    logger.info("Setting intensity", correlation_id=correlation_id, intensity=data.intensity)
    state = await ops.set_intensity(data)
    logger.info("Intensity set", correlation_id=correlation_id, intensity=data.intensity)
    return {"status": "success", "state": state}

@app.post("/toggle_system")
async def api_toggle_system(data: ToggleSystemData):
    correlation_id = str(uuid.uuid4())
    logger.info("Toggling system", correlation_id=correlation_id, isSystemOn=data.isSystemOn)
    state = await ops.toggle_system(data)
    logger.info("System toggled", correlation_id=correlation_id, isSystemOn=data.isSystemOn)
    return {"status": "success", "state": state}

@app.get("/available_scenes")
async def api_available_scenes():
    correlation_id = str(uuid.uuid4())
    logger.info("Listing available scenes", correlation_id=correlation_id)
    state = ops._get_state()
    logger.info("Available scenes listed", correlation_id=correlation_id, scenes=state["available_scenes"])
    return {"available_scenes": state["available_scenes"]}

@app.post("/set_timer")
async def api_set_timer(data: SetTimerData):
    correlation_id = str(uuid.uuid4())
    logger.info("Setting timers", correlation_id=correlation_id, timers=[timer.dict() for timer in data.timers])
    state = await ops.set_timer(data)
    if "error" in state:
        logger.error("Failed to set timers", correlation_id=correlation_id, error=state["error"])
        return {"error": state["error"]}
    logger.info("Timers set", correlation_id=correlation_id, timers=state["system_timers"])
    return {"status": "success", "state": state}

@app.get("/get_timers")
async def api_get_timers():
    correlation_id = str(uuid.uuid4())
    logger.info("Getting timers", correlation_id=correlation_id)
    state = ops._get_state()
    logger.info("Timers retrieved", correlation_id=correlation_id, timers=state.get("system_timers", []))
    return {"timers": state.get("system_timers", []), "isTimerEnabled": state.get("isTimerEnabled", False)}

@app.post("/toggle_timer")
async def api_toggle_timer(data: ToggleTimerData):
    correlation_id = str(uuid.uuid4())
    logger.info("Toggling timers", correlation_id=correlation_id, enable=data.enable)
    state = ops._get_state()
    state["isTimerEnabled"] = data.enable
    ops._set_state(state)
    logger.info("Timers toggled", correlation_id=correlation_id, enable=data.enable)
    return {"status": "success", "isTimerEnabled": state["isTimerEnabled"], "timers": state["system_timers"]}

@app.post("/reset_timers")
async def api_reset_timers():
    correlation_id = str(uuid.uuid4())
    logger.info("Resetting timers", correlation_id=correlation_id)
    state = ops.reset_timers()
    logger.info("Timers reset", correlation_id=correlation_id)
    return {"status": "success", "state": state}

async def start_background_tasks():
    correlation_id = str(uuid.uuid4())
    logger.info("Starting background tasks", correlation_id=correlation_id)
    logger.info("Loading scenes...", correlation_id=correlation_id)
    available_scenes = load_scenes()
    state = ops._get_state()
    state["available_scenes"] = available_scenes
    ops._set_state(state)
    logger.info("Updated state with available scenes", correlation_id=correlation_id, scene_count=len(available_scenes))
    logger.info("Starting timer scheduler...", correlation_id=correlation_id)
    task = asyncio.create_task(ops.run_timer_scheduler())
    return [task]

if __name__ == "__main__":
    soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft_limit < 1024:
        resource.setrlimit(resource.RLIMIT_NOFILE, (1024, hard_limit))
    config_uvicorn = uvicorn.Config(
        app=app,
        host=config['microservices']['scheduler_service']['host'],
        port=config['microservices']['scheduler_service']['port']
    )
    server = uvicorn.Server(config_uvicorn)
    async def run_all():
        tasks = await start_background_tasks()
        await server.serve()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    asyncio.run(run_all())