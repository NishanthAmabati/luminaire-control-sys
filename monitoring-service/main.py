import asyncio
import uvicorn
from fastapi import FastAPI
import yaml
import resource
import logging
from logging.handlers import TimedRotatingFileHandler
import redis
from .monitoring_operations import MonitoringOperations
from .models import SystemStats
import time

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

app = FastAPI(title="Monitoring Service", version="1.0.0")

ops = MonitoringOperations()

redis_client = redis.Redis(
    host=config["redis"]["host"],
    port=config["redis"]["port"],
    db=config["redis"]["db"],
    password=config["redis"]["password"]
)

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/system_stats", response_model=SystemStats)
async def api_system_stats():
    try:
        cpu_str = redis_client.get("cpu_percent")
        mem_str = redis_client.get("mem_percent")
        temp_str = redis_client.get("temperature")
        cpu_percent = float(cpu_str) if cpu_str else 0.0
        mem_percent = float(mem_str) if mem_str else 0.0
        temperature = float(temp_str) if temp_str and temp_str != b"null" else None
        logging.debug(f"Fetched system stats: cpu={cpu_percent}, mem={mem_percent}, temp={temperature}")
        return SystemStats(cpu_percent=cpu_percent, mem_percent=mem_percent, temperature=temperature)
    except Exception as e:
        logging.error(f"Error fetching system stats: {e}")
        return SystemStats(cpu_percent=0.0, mem_percent=0.0, temperature=None)

async def start_background_tasks():
    logging.info("Starting system stats broadcast...")
    task = asyncio.create_task(ops.broadcast_system_stats())
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
        port=config["microservices"]["monitoring_port"]
    )
    server = uvicorn.Server(config_uvicorn)

    async def run_all():
        tasks = await start_background_tasks()
        await server.serve()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    asyncio.run(run_all())