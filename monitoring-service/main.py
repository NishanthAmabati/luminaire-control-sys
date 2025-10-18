import asyncio
import uvicorn
from fastapi import FastAPI
import yaml
import resource
import logging
import time
import uuid
import redis
import structlog
from monitoring_service.monitoring_operations import MonitoringOperations
from monitoring_service.models import SystemStats

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
logger = structlog.get_logger(service="monitoring-service")

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
    correlation_id = str(uuid.uuid4())
    logger.info("Health check", correlation_id=correlation_id, endpoint="/health")
    return {"status": "healthy"}

@app.get("/system_stats", response_model=SystemStats)
async def api_system_stats():
    correlation_id = str(uuid.uuid4())
    logger.info("Fetching system stats", correlation_id=correlation_id, endpoint="/system_stats")
    try:
        cpu_str = redis_client.get("cpu_percent")
        mem_str = redis_client.get("mem_percent")
        temp_str = redis_client.get("temperature")
        cpu_percent = float(cpu_str) if cpu_str else 0.0
        mem_percent = float(mem_str) if mem_str else 0.0
        temperature = float(temp_str) if temp_str and temp_str != b"null" else None
        logger.debug("System stats fetched", correlation_id=correlation_id, cpu_percent=cpu_percent, mem_percent=mem_percent, temperature=temperature)
        logger.info("System stats retrieved", correlation_id=correlation_id, cpu_percent=cpu_percent, mem_percent=mem_percent, temperature=temperature)
        return SystemStats(cpu_percent=cpu_percent, mem_percent=mem_percent, temperature=temperature)
    except Exception as e:
        logger.error("Error fetching system stats", correlation_id=correlation_id, error=str(e))
        return SystemStats(cpu_percent=0.0, mem_percent=0.0, temperature=None)

async def start_background_tasks():
    correlation_id = str(uuid.uuid4())
    logger.info("Starting background tasks", correlation_id=correlation_id)
    logger.info("Starting system stats broadcast", correlation_id=correlation_id)
    task = asyncio.create_task(ops.broadcast_system_stats())
    return [task]

if __name__ == "__main__":
    soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft_limit < 1024:
        resource.setrlimit(resource.RLIMIT_NOFILE, (1024, hard_limit))
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