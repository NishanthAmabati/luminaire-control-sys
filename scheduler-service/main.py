import asyncio
import uvicorn
from fastapi import FastAPI
import yaml
import resource
import logging
from .scheduler_operations import SchedulerOperations
from .scene_loader import load_scenes
from .models import *
import pickle
import redis

# Configure logging
logging.basicConfig(level=logging.INFO)

# Load config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

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
    return {"status": "healthy"}

@app.post("/set_mode")
async def api_set_mode(data: SetModeData):
    state = await ops.set_mode(data)
    return {"status": "success", "state": state}

@app.post("/load_scene")
async def api_load_scene(data: LoadSceneData):
    state = await ops.load_scene(data)
    return {"status": "success", "state": state}

@app.post("/activate_scene")
async def api_activate_scene(data: ActivateSceneData):
    state = await ops.activate_scene(data)
    return {"status": "success", "state": state}

@app.post("/stop_scheduler")
async def api_stop_scheduler():
    ops.stop_scheduler()
    return {"status": "stopped"}

@app.post("/pause_resume")
async def api_pause_resume(data: PauseResumeData):
    if data.pause:
        ops.stop_scheduler()
        return {"status": "paused"}
    else:
        state = ops._get_state()
        if state["current_scene"]:
            await ops.activate_scene(ActivateSceneData(scene=state["current_scene"]))
            return {"status": "resumed"}
        return {"status": "no_scene_to_resume"}

@app.post("/manual_override")
async def api_manual_override(data: ManualOverrideData):
    state = await ops.manual_override(data)
    return {"status": "success", "state": state}

@app.post("/adjust_light")
async def api_adjust_light(data: AdjustLightData):
    state = await ops.adjust_light(data)
    return {"status": "success", "state": state}

@app.post("/send_all")
async def api_send_all(data: SendAllData):
    state = await ops.send_all(data)
    return {"status": "success", "state": state}

@app.post("/set_cct")
async def api_set_cct(data: SetCCTData):
    state = await ops.set_cct(data)
    return {"status": "success", "state": state}

@app.post("/set_intensity")
async def api_set_intensity(data: SetIntensityData):
    state = await ops.set_intensity(data)
    return {"status": "success", "state": state}

@app.post("/toggle_system")
async def api_toggle_system(data: ToggleSystemData):
    state = await ops.toggle_system(data)
    return {"status": "success", "state": state}

@app.get("/available_scenes")
async def api_available_scenes():
    state = ops._get_state()
    return {"available_scenes": state["available_scenes"]}

@app.post("/set_timer")
async def api_set_timer(data: SetTimerData):
    """Set system on/off timers."""
    state = await ops.set_timer(data)
    return {"status": "success", "state": state} if "error" not in state else {"error": state["error"]}

@app.get("/get_timers")
async def api_get_timers():
    """Get current system timers."""
    state = ops._get_state()
    return {"timers": state.get("system_timers", []), "isTimerEnabled": state.get("isTimerEnabled", False)}

@app.post("/toggle_timer")
async def api_toggle_timer(data: ToggleTimerData):
    """Enable or disable timers."""
    state = ops._get_state()
    state["isTimerEnabled"] = data.enable
    ops._set_state(state)
    logging.info(f"Timers {'enabled' if data.enable else 'disabled'}")
    return {"status": "success", "isTimerEnabled": state["isTimerEnabled"], "timers": state["system_timers"]}

@app.post("/reset_timers")
async def api_reset_timers():
    """Reset all timers."""
    state = ops.reset_timers()
    return {"status": "success", "state": state}

async def start_background_tasks():
    """Start scheduler tasks in background."""
    logging.info("Loading scenes...")
    available_scenes = load_scenes()
    # Update the SchedulerOperations state with available_scenes
    state = ops._get_state()
    state["available_scenes"] = available_scenes
    ops._set_state(state)
    logging.info(f"Updated state with {len(available_scenes)} available scenes")
    logging.info("Starting timer scheduler...")
    task = asyncio.create_task(ops.run_timer_scheduler())
    return [task]

if __name__ == "__main__":
    # Set resource limit
    soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft_limit < 1024:
        resource.setrlimit(resource.RLIMIT_NOFILE, (1024, hard_limit))

    # Start uvicorn with custom startup hook
    config_uvicorn = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=config["microservices"]["scheduler_port"]
    )
    server = uvicorn.Server(config_uvicorn)

    # Run tasks and uvicorn in same loop
    async def run_all():
        tasks = await start_background_tasks()
        await server.serve()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    asyncio.run(run_all())