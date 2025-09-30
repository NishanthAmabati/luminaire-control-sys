import asyncio
import uvicorn
from fastapi import FastAPI
import yaml
import resource
import logging
import httpx
import time
from logging.handlers import TimedRotatingFileHandler
from .api_operations import status_loop
from .models import *

# Load config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Configure logging
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

app = FastAPI(title="API Service", version="1.0.0")

@app.get("/health")
async def health():
    """Health check endpoint for monitoring."""
    return {"status": "healthy"}

@app.post("/api/set_mode")
async def api_set_mode(data: SetModeData):
    """Set auto/manual mode by calling Scheduler Service."""
    scheduler_url = f"http://{config['server']['host']}:{config['microservices']['scheduler_port']}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/set_mode", json=data.dict())
            return resp.json() if resp.status_code == 200 else {"error": f"Failed to set mode: {resp.text}"}
        except httpx.HTTPError as e:
            logging.error(f"HTTP error in set_mode: {e}")
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/load_scene")
async def api_load_scene(data: LoadSceneData):
    """Load a scene by calling Scheduler Service."""
    scheduler_url = f"http://{config['server']['host']}:{config['microservices']['scheduler_port']}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/load_scene", json=data.dict())
            return resp.json() if resp.status_code == 200 else {"error": f"Failed to load scene: {resp.text}"}
        except httpx.HTTPError as e:
            logging.error(f"HTTP error in load_scene: {e}")
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/activate_scene")
async def api_activate_scene(data: ActivateSceneData):
    """Activate a scene by calling Scheduler Service."""
    scheduler_url = f"http://{config['server']['host']}:{config['microservices']['scheduler_port']}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/activate_scene", json=data.dict())
            return resp.json() if resp.status_code == 200 else {"error": f"Failed to activate scene: {resp.text}"}
        except httpx.HTTPError as e:
            logging.error(f"HTTP error in activate_scene: {e}")
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/stop_scheduler")
async def api_stop_scheduler():
    """Stop the scheduler by calling Scheduler Service."""
    scheduler_url = f"http://{config['server']['host']}:{config['microservices']['scheduler_port']}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/stop_scheduler")
            return {"status": "stopped"} if resp.status_code == 200 else {"error": f"Failed to stop scheduler: {resp.text}"}
        except httpx.HTTPError as e:
            logging.error(f"HTTP error in stop_scheduler: {e}")
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/pause_resume")
async def api_pause_resume(data: PauseResumeData):
    """Pause or resume the scheduler by calling Scheduler Service."""
    scheduler_url = f"http://{config['server']['host']}:{config['microservices']['scheduler_port']}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/pause_resume", json=data.dict())
            return resp.json() if resp.status_code == 200 else {"error": f"Failed to pause/resume: {resp.text}"}
        except httpx.HTTPError as e:
            logging.error(f"HTTP error in pause_resume: {e}")
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/manual_override")
async def api_manual_override(data: ManualOverrideData):
    """Set manual override by calling Scheduler Service."""
    scheduler_url = f"http://{config['server']['host']}:{config['microservices']['scheduler_port']}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/manual_override", json=data.dict())
            return resp.json() if resp.status_code == 200 else {"error": f"Failed to set manual override: {resp.text}"}
        except httpx.HTTPError as e:
            logging.error(f"HTTP error in manual_override: {e}")
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/adjust_light")
async def api_adjust_light(data: AdjustLightData):
    """Adjust light settings by calling Scheduler Service."""
    scheduler_url = f"http://{config['server']['host']}:{config['microservices']['scheduler_port']}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/adjust_light", json=data.dict())
            return resp.json() if resp.status_code == 200 else {"error": f"Failed to adjust light: {resp.text}"}
        except httpx.HTTPError as e:
            logging.error(f"HTTP error in adjust_light: {e}")
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/send_all")
async def api_send_all(data: SendAllData):
    """Send CW/WW/intensity to all devices via Scheduler Service."""
    scheduler_url = f"http://{config['server']['host']}:{config['microservices']['scheduler_port']}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/send_all", json=data.dict())
            return resp.json() if resp.status_code == 200 else {"error": f"Failed to send all: {resp.text}"}
        except httpx.HTTPError as e:
            logging.error(f"HTTP error in send_all: {e}")
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/set_cct")
async def api_set_cct(data: SetCCTData):
    """Set CCT by calling Scheduler Service."""
    scheduler_url = f"http://{config['server']['host']}:{config['microservices']['scheduler_port']}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/set_cct", json=data.dict())
            return resp.json() if resp.status_code == 200 else {"error": f"Failed to set CCT: {resp.text}"}
        except httpx.HTTPError as e:
            logging.error(f"HTTP error in set_cct: {e}")
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/set_intensity")
async def api_set_intensity(data: SetIntensityData):
    """Set intensity by calling Scheduler Service."""
    scheduler_url = f"http://{config['server']['host']}:{config['microservices']['scheduler_port']}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/set_intensity", json=data.dict())
            return resp.json() if resp.status_code == 200 else {"error": f"Failed to set intensity: {resp.text}"}
        except httpx.HTTPError as e:
            logging.error(f"HTTP error in set_intensity: {e}")
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/toggle_system")
async def api_toggle_system(data: ToggleSystemData):
    """Toggle system on/off by calling Scheduler Service."""
    scheduler_url = f"http://{config['server']['host']}:{config['microservices']['scheduler_port']}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/toggle_system", json=data.dict())
            return resp.json() if resp.status_code == 200 else {"error": f"Failed to toggle system: {resp.text}"}
        except httpx.HTTPError as e:
            logging.error(f"HTTP error in toggle_system: {e}")
            return {"error": f"HTTP error: {str(e)}"}

@app.get("/api/available_scenes")
async def api_available_scenes():
    """Get available scenes from Scheduler Service."""
    scheduler_url = f"http://{config['server']['host']}:{config['microservices']['scheduler_port']}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{scheduler_url}/available_scenes")
            return resp.json() if resp.status_code == 200 else {"error": f"Failed to get scenes: {resp.text}"}
        except httpx.HTTPError as e:
            logging.error(f"HTTP error in available_scenes: {e}")
            return {"error": f"HTTP error: {str(e)}"}

@app.get("/api/system_stats")
async def api_system_stats():
    """Get system stats from Monitoring Service."""
    monitoring_url = f"http://{config['server']['host']}:{config['microservices']['monitoring_port']}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{monitoring_url}/system_stats")
            return resp.json() if resp.status_code == 200 else {"error": f"Failed to get stats: {resp.text}"}
        except httpx.HTTPError as e:
            logging.error(f"HTTP error in system_stats: {e}")
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/set_timer")
async def api_set_timer(data: SetTimerData):
    """Set system on/off timers via Scheduler Service."""
    scheduler_url = f"http://{config['server']['host']}:{config['microservices']['scheduler_port']}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/set_timer", json=data.dict())
            return resp.json() if resp.status_code == 200 else {"error": f"Failed to set timers: {resp.text}"}
        except httpx.HTTPError as e:
            logging.error(f"HTTP error in set_timer: {e}")
            return {"error": f"HTTP error: {str(e)}"}

@app.get("/api/get_timers")
async def api_get_timers():
    """Get current system timers from Scheduler Service."""
    scheduler_url = f"http://{config['server']['host']}:{config['microservices']['scheduler_port']}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{scheduler_url}/get_timers")
            return resp.json() if resp.status_code == 200 else {"error": f"Failed to get timers: {resp.text}"}
        except httpx.HTTPError as e:
            logging.error(f"HTTP error in get_timers: {e}")
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/toggle_timer")
async def api_toggle_timer(data: ToggleTimerData):
    """Enable or disable timers via Scheduler Service."""
    scheduler_url = f"http://{config['server']['host']}:{config['microservices']['scheduler_port']}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/toggle_timer", json=data.dict())
            return resp.json() if resp.status_code == 200 else {"error": f"Failed to toggle timer: {resp.text}"}
        except httpx.HTTPError as e:
            logging.error(f"HTTP error in toggle_timer: {e}")
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/reset_timers")
async def api_reset_timers():
    """Reset all timers via Scheduler Service."""
    scheduler_url = f"http://{config['server']['host']}:{config['microservices']['scheduler_port']}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/reset_timers")
            return resp.json() if resp.status_code == 200 else {"error": f"Failed to reset timers: {resp.text}"}
        except httpx.HTTPError as e:
            logging.error(f"HTTP error in reset_timers: {e}")
            return {"error": f"HTTP error: {str(e)}"}

async def main():
    """Main entrypoint: Start background tasks and FastAPI."""
    # Set file descriptor limit
    soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft_limit < 1024:
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (1024, hard_limit))
            logging.debug("Increased file descriptor limit to 1024")
        except Exception as e:
            logging.warning(f"Failed to increase file descriptor limit: {e}")

    # Start background task
    asyncio.create_task(status_loop())
    
    # Start FastAPI
    config_uvicorn = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=config["microservices"]["api_port"],
        log_level="info"
    )
    server = uvicorn.Server(config_uvicorn)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())