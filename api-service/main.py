import asyncio
import uvicorn
from fastapi import FastAPI
import yaml
import resource
import logging
import httpx
import time
import os
import uuid
import structlog
from logging.handlers import TimedRotatingFileHandler
from api_service.api_operations import status_loop
from api_service.models import *

# Load config
with open("/app/config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Structured logging setup
log_dir = "/app/logs/api-service"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
timestamp = time.strftime("%Y-%m-%d.log")
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
handler = logging.handlers.TimedRotatingFileHandler(
    f"{log_dir}/{timestamp}",
    when=config["logging"]["rotation_when"],
    interval=config["logging"]["rotation_interval"],
    backupCount=config["logging"]["rotation_backup_count"]
)
logging.basicConfig(
    level=getattr(logging, config["logging"]["level"]),
    format="%(message)s",
    handlers=[handler, logging.StreamHandler()]
)
logger = structlog.get_logger(service="api-service")

app = FastAPI(title="API Service", version="1.0.0")
scheduler_url = f"http://{config['microservices']['scheduler_service']['host']}:{config['microservices']['scheduler_service']['port']}"
monitoring_url = f"http://{config['microservices']['monitoring_service']['host']}:{config['microservices']['monitoring_service']['port']}"

@app.get("/health")
async def health():
    correlation_id = str(uuid.uuid4())
    logger.info("Health check", correlation_id=correlation_id, endpoint="/health")
    return {"status": "healthy"}

@app.post("/api/set_mode")
async def api_set_mode(data: SetModeData):
    correlation_id = str(uuid.uuid4())
    logger.info("Setting mode", correlation_id=correlation_id, auto=data.auto)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/set_mode", json=data.dict())
            if resp.status_code == 200:
                logger.info("Mode set", correlation_id=correlation_id, auto=data.auto)
                return resp.json()
            logger.error("Failed to set mode", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to set mode: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in set_mode", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/load_scene")
async def api_load_scene(data: LoadSceneData):
    correlation_id = str(uuid.uuid4())
    logger.info("Loading scene", correlation_id=correlation_id, scene=data.scene)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/load_scene", json=data.dict())
            if resp.status_code == 200:
                logger.info("Scene loaded", correlation_id=correlation_id, scene=data.scene)
                return resp.json()
            logger.error("Failed to load scene", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to load scene: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in load_scene", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/activate_scene")
async def api_activate_scene(data: ActivateSceneData):
    correlation_id = str(uuid.uuid4())
    logger.info("Activating scene", correlation_id=correlation_id, scene=data.scene)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/activate_scene", json=data.dict())
            if resp.status_code == 200:
                logger.info("Scene activated", correlation_id=correlation_id, scene=data.scene)
                return resp.json()
            logger.error("Failed to activate scene", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to activate scene: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in activate_scene", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/stop_scheduler")
async def api_stop_scheduler():
    correlation_id = str(uuid.uuid4())
    logger.info("Stopping scheduler", correlation_id=correlation_id)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/stop_scheduler")
            if resp.status_code == 200:
                logger.info("Scheduler stopped", correlation_id=correlation_id)
                return {"status": "stopped"}
            logger.error("Failed to stop scheduler", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to stop scheduler: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in stop_scheduler", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/pause_resume")
async def api_pause_resume(data: PauseResumeData):
    correlation_id = str(uuid.uuid4())
    logger.info("Pausing/resuming scheduler", correlation_id=correlation_id, pause=data.pause)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/pause_resume", json=data.dict())
            if resp.status_code == 200:
                logger.info("Scheduler pause/resume completed", correlation_id=correlation_id, pause=data.pause)
                return resp.json()
            logger.error("Failed to pause/resume", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to pause/resume: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in pause_resume", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/manual_override")
async def api_manual_override(data: ManualOverrideData):
    correlation_id = str(uuid.uuid4())
    logger.info("Setting manual override", correlation_id=correlation_id, override=data.override)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/manual_override", json=data.dict())
            if resp.status_code == 200:
                logger.info("Manual override set", correlation_id=correlation_id, override=data.override)
                return resp.json()
            logger.error("Failed to set manual override", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to set manual override: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in manual_override", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/adjust_light")
async def api_adjust_light(data: AdjustLightData):
    correlation_id = str(uuid.uuid4())
    logger.info("Adjusting light", correlation_id=correlation_id, light_type=data.light_type, delta=data.delta)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/adjust_light", json=data.dict())
            if resp.status_code == 200:
                logger.info("Light adjusted", correlation_id=correlation_id, light_type=data.light_type, delta=data.delta)
                return resp.json()
            logger.error("Failed to adjust light", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to adjust light: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in adjust_light", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/send_all")
async def api_send_all(data: SendAllData):
    correlation_id = str(uuid.uuid4())
    logger.info("Sending to all", correlation_id=correlation_id, cw=data.cw, ww=data.ww, intensity=data.intensity)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/send_all", json=data.dict())
            if resp.status_code == 200:
                logger.info("Sent to all", correlation_id=correlation_id, cw=data.cw, ww=data.ww, intensity=data.intensity)
                return resp.json()
            logger.error("Failed to send all", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to send all: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in send_all", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/set_cct")
async def api_set_cct(data: SetCCTData):
    correlation_id = str(uuid.uuid4())
    logger.info("Setting CCT", correlation_id=correlation_id, cct=data.cct)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/set_cct", json=data.dict())
            if resp.status_code == 200:
                logger.info("CCT set", correlation_id=correlation_id, cct=data.cct)
                return resp.json()
            logger.error("Failed to set CCT", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to set CCT: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in set_cct", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/set_intensity")
async def api_set_intensity(data: SetIntensityData):
    correlation_id = str(uuid.uuid4())
    logger.info("Setting intensity", correlation_id=correlation_id, intensity=data.intensity)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/set_intensity", json=data.dict())
            if resp.status_code == 200:
                logger.info("Intensity set", correlation_id=correlation_id, intensity=data.intensity)
                return resp.json()
            logger.error("Failed to set intensity", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to set intensity: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in set_intensity", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/toggle_system")
async def api_toggle_system(data: ToggleSystemData):
    correlation_id = str(uuid.uuid4())
    logger.info("Toggling system", correlation_id=correlation_id, isSystemOn=data.isSystemOn)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/toggle_system", json=data.dict())
            if resp.status_code == 200:
                logger.info("System toggled", correlation_id=correlation_id, isSystemOn=data.isSystemOn)
                return resp.json()
            logger.error("Failed to toggle system", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to toggle system: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in toggle_system", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.get("/api/available_scenes")
async def api_available_scenes():
    correlation_id = str(uuid.uuid4())
    logger.info("Fetching available scenes", correlation_id=correlation_id)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{scheduler_url}/available_scenes")
            if resp.status_code == 200:
                logger.info("Available scenes fetched", correlation_id=correlation_id)
                return resp.json()
            logger.error("Failed to get scenes", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to get scenes: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in available_scenes", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.get("/api/system_stats")
async def api_system_stats():
    correlation_id = str(uuid.uuid4())
    logger.info("Fetching system stats", correlation_id=correlation_id)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{monitoring_url}/system_stats")
            if resp.status_code == 200:
                logger.info("System stats fetched", correlation_id=correlation_id)
                return resp.json()
            logger.error("Failed to get stats", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to get stats: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in system_stats", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/set_timer")
async def api_set_timer(data: SetTimerData):
    correlation_id = str(uuid.uuid4())
    logger.info("Setting timers", correlation_id=correlation_id, timers=[timer.dict() for timer in data.timers])
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/set_timer", json=data.dict())
            if resp.status_code == 200:
                logger.info("Timers set", correlation_id=correlation_id, timer_count=len(data.timers))
                return resp.json()
            logger.error("Failed to set timers", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to set timers: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in set_timer", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.get("/api/get_timers")
async def api_get_timers():
    correlation_id = str(uuid.uuid4())
    logger.info("Fetching timers", correlation_id=correlation_id)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{scheduler_url}/get_timers")
            if resp.status_code == 200:
                logger.info("Timers fetched", correlation_id=correlation_id)
                return resp.json()
            logger.error("Failed to get timers", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to get timers: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in get_timers", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/toggle_timer")
async def api_toggle_timer(data: ToggleTimerData):
    correlation_id = str(uuid.uuid4())
    logger.info("Toggling timers", correlation_id=correlation_id, enable=data.enable)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/toggle_timer", json=data.dict())
            if resp.status_code == 200:
                logger.info("Timers toggled", correlation_id=correlation_id, enable=data.enable)
                return resp.json()
            logger.error("Failed to toggle timer", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to toggle timer: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in toggle_timer", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/reset_timers")
async def api_reset_timers():
    correlation_id = str(uuid.uuid4())
    logger.info("Resetting timers", correlation_id=correlation_id)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/reset_timers")
            if resp.status_code == 200:
                logger.info("Timers reset", correlation_id=correlation_id)
                return resp.json()
            logger.error("Failed to reset timers", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to reset timers: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in reset_timers", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

async def main():
    correlation_id = str(uuid.uuid4())
    logger.info("Starting API service", correlation_id=correlation_id)
    soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft_limit < 1024:
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (1024, hard_limit))
            logger.debug("Increased file descriptor limit to 1024", correlation_id=correlation_id)
        except Exception as e:
            logger.warning("Failed to increase file descriptor limit", correlation_id=correlation_id, error=str(e))
    asyncio.create_task(status_loop())
    config_uvicorn = uvicorn.Config(
        app,
        host=config['microservices']['api_service']['host'],
        port=config["microservices"]['api_service']['port'],
        log_level=config['microservices']['api_service']['log_level']
    )
    server = uvicorn.Server(config_uvicorn)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())