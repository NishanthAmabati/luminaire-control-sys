import asyncio
import uvicorn
from fastapi import FastAPI, Request
import yaml
import resource
import logging
import time
import uuid
import redis
import structlog
import psutil
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Info,
    ProcessCollector,
    PlatformCollector,
)
from starlette.responses import Response
from monitoring_service.monitoring_operations import MonitoringOperations
from monitoring_service.models import SystemStats

# Load config
with open("/app/config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Structured logging setup – JSON to STDOUT only
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
logging.basicConfig(
    level=getattr(logging, config["logging"]["level"]),
    format="%(message)s",
    handlers=[logging.StreamHandler()],
)
logger = structlog.get_logger(service="monitoring-service")

app = FastAPI(title="Monitoring Service", version="1.0.0")
ops = MonitoringOperations()

redis_client = redis.Redis(
    host=config["redis"]["host"],
    port=config["redis"]["port"],
    db=config["redis"]["db"],
    password=config["redis"]["password"],
)

# --- Prometheus Metrics ---
REGISTRY = CollectorRegistry()
ProcessCollector(registry=REGISTRY)
PlatformCollector(registry=REGISTRY)
REQUEST_COUNT = Counter('monitoring_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'http_status'], registry=REGISTRY)
REQUEST_LATENCY = Histogram('monitoring_request_latency_seconds', 'Request latency', ['endpoint'], registry=REGISTRY)
ERROR_COUNT = Counter('monitoring_api_errors_total', 'Total Monitoring API errors', ['endpoint'], registry=REGISTRY)
CPU_USAGE = Gauge('monitoring_cpu_usage_percent', 'CPU usage percent', registry=REGISTRY)
MEM_USAGE = Gauge('monitoring_memory_usage_percent', 'Memory usage percent', registry=REGISTRY)
UPTIME = Gauge('monitoring_uptime_seconds', 'Service uptime in seconds', registry=REGISTRY)
SERVICE_INFO = Info('monitoring_service', 'Monitoring service build info', registry=REGISTRY)
SERVICE_INFO.info({'version': '1.0.0', 'service': 'monitoring-service'})
START_TIME = time.time()

@app.middleware('http')
async def prometheus_request_metrics(request: Request, call_next):
    endpoint = request.url.path
    method = request.method
    start = time.time()
    try:
        response = await call_next(request)
        status = response.status_code
    except Exception:
        ERROR_COUNT.labels(endpoint=endpoint).inc()
        logger.exception("Request error", extra={"endpoint": endpoint})
        raise
    latency = time.time() - start
    REQUEST_LATENCY.labels(endpoint=endpoint).observe(latency)
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, http_status=status).inc()
    return response

@app.on_event("startup")
async def on_startup():
    correlation_id = str(uuid.uuid4())
    logger.info("Monitoring service startup", correlation_id=correlation_id)

@app.get("/metrics")
async def metrics():
    CPU_USAGE.set(psutil.cpu_percent())
    MEM_USAGE.set(psutil.virtual_memory().percent)
    UPTIME.set(time.time() - START_TIME)
    data = generate_latest(REGISTRY)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)

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
        port=config["microservices"]["monitoring_service"]["port"],
    )
    server = uvicorn.Server(config_uvicorn)
    async def run_all():
        tasks = await start_background_tasks()
        await server.serve()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    asyncio.run(run_all())