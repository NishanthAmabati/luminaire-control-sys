"""
Timer Service - Production-Grade Microservice for System Timers

This service provides:
- Robust timer scheduling with immediate triggering
- RESTful API for timer management
- Redis-backed state persistence
- Comprehensive logging and error handling
- Health check endpoint
- Prometheus metrics support
"""

import asyncio
import os
import logging
import structlog
import yaml
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import redis.asyncio as aioredis
import uuid

from models import SetTimerData, ToggleTimerData, TimersResponse, TimerStatusResponse
from timer_operations import TimerOperations

# Load configuration from config.yaml
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Get timer service config
timer_config = config["microservices"]["timer_service"]
SERVICE_PORT = timer_config["port"]
LOG_LEVEL = timer_config["log_level"]

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(service="timer-service")
logging.basicConfig(level=LOG_LEVEL, format="%(message)s")

# Environment variables
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# Get API service URL from config
api_config = config["microservices"]["api_service"]
API_SERVICE_URL = f"http://{api_config['host']}:{api_config['port']}"

# Prometheus metrics
REQUEST_COUNT = Counter('timer_requests_total', 'Total requests to timer service', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('timer_request_duration_seconds', 'Request duration', ['method', 'endpoint'])
ACTIVE_TIMERS = Gauge('timer_active_count', 'Number of active timers')
TIMER_TRIGGERS = Counter('timer_triggers_total', 'Total timer triggers', ['action'])
TIMER_ERRORS = Counter('timer_errors_total', 'Total timer errors', ['type'])

# Global timer operations instance
timer_ops: TimerOperations = None
timer_task: asyncio.Task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown"""
    global timer_ops, timer_task
    
    logger.info("Starting timer-service...")
    
    # Initialize Redis connection
    try:
        redis_client = await aioredis.from_url(
            f"redis://{REDIS_HOST}:{REDIS_PORT}",
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5
        )
        await redis_client.ping()
        logger.info("Redis connection established", host=REDIS_HOST, port=REDIS_PORT)
    except Exception as e:
        logger.error("Failed to connect to Redis", error=str(e))
        raise
        
    # Initialize timer operations
    timer_ops = TimerOperations(redis_client, API_SERVICE_URL)
    await timer_ops.initialize()
    
    # Start timer loop in background
    timer_task = asyncio.create_task(timer_ops.run_timer_loop())
    logger.info("Timer loop started in background")
    
    logger.info("Timer-service started successfully", port=SERVICE_PORT)
    
    yield
    
    # Shutdown
    logger.info("Shutting down timer-service...")
    await timer_ops.stop()
    
    if timer_task and not timer_task.done():
        timer_task.cancel()
        try:
            await timer_task
        except asyncio.CancelledError:
            pass
            
    await redis_client.close()
    logger.info("Timer-service shutdown complete")


# Initialize FastAPI app
app = FastAPI(
    title="Timer Service",
    description="Production-grade timer scheduling microservice",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        # Check if timer operations is initialized
        if timer_ops is None:
            raise HTTPException(status_code=503, detail="Service not initialized")
            
        # Check Redis connection
        await timer_ops.redis_client.ping()
        
        return {
            "status": "healthy",
            "service": "timer-service",
            "timers_enabled": timer_ops.is_enabled,
            "active_timers": len(timer_ops.timers)
        }
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/set_timer", response_model=TimerStatusResponse)
async def set_timer(data: SetTimerData):
    """
    Set system timers
    
    This endpoint:
    - Validates timer format (HH:MM)
    - Clears previous trigger state
    - Allows immediate triggering if current time >= scheduled time
    - Persists configuration to Redis
    """
    correlation_id = str(uuid.uuid4())
    logger.info("Setting timers", correlation_id=correlation_id, timer_count=len(data.timers))
    
    try:
        with REQUEST_DURATION.labels(method='POST', endpoint='/set_timer').time():
            result = await timer_ops.set_timers(data)
            
            if result.get("status") == "error":
                REQUEST_COUNT.labels(method='POST', endpoint='/set_timer', status='error').inc()
                TIMER_ERRORS.labels(type='set_timer').inc()
                raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
                
            REQUEST_COUNT.labels(method='POST', endpoint='/set_timer', status='success').inc()
            ACTIVE_TIMERS.set(len(data.timers))
            
            logger.info("Timers set successfully", correlation_id=correlation_id, timer_count=len(data.timers))
            return result
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to set timers", correlation_id=correlation_id, error=str(e))
        TIMER_ERRORS.labels(type='set_timer').inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/get_timers", response_model=TimersResponse)
async def get_timers():
    """Get current timer configuration"""
    correlation_id = str(uuid.uuid4())
    logger.info("Getting timers", correlation_id=correlation_id)
    
    try:
        with REQUEST_DURATION.labels(method='GET', endpoint='/get_timers').time():
            result = await timer_ops.get_timers()
            REQUEST_COUNT.labels(method='GET', endpoint='/get_timers', status='success').inc()
            logger.info("Timers retrieved", correlation_id=correlation_id, timer_count=len(result["timers"]))
            return result
            
    except Exception as e:
        logger.error("Failed to get timers", correlation_id=correlation_id, error=str(e))
        TIMER_ERRORS.labels(type='get_timers').inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/toggle_timer", response_model=TimerStatusResponse)
async def toggle_timer(data: ToggleTimerData):
    """Enable or disable the timer system"""
    correlation_id = str(uuid.uuid4())
    logger.info("Toggling timer system", correlation_id=correlation_id, enable=data.enable)
    
    try:
        with REQUEST_DURATION.labels(method='POST', endpoint='/toggle_timer').time():
            result = await timer_ops.toggle_timers(data.enable)
            
            if result.get("status") == "error":
                REQUEST_COUNT.labels(method='POST', endpoint='/toggle_timer', status='error').inc()
                TIMER_ERRORS.labels(type='toggle_timer').inc()
                raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
                
            REQUEST_COUNT.labels(method='POST', endpoint='/toggle_timer', status='success').inc()
            logger.info("Timer system toggled", correlation_id=correlation_id, enabled=data.enable)
            return result
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to toggle timer system", correlation_id=correlation_id, error=str(e))
        TIMER_ERRORS.labels(type='toggle_timer').inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reset_timers", response_model=TimerStatusResponse)
async def reset_timers():
    """Reset all timers and disable the system"""
    correlation_id = str(uuid.uuid4())
    logger.info("Resetting timers", correlation_id=correlation_id)
    
    try:
        with REQUEST_DURATION.labels(method='POST', endpoint='/reset_timers').time():
            result = await timer_ops.reset_timers()
            
            if result.get("status") == "error":
                REQUEST_COUNT.labels(method='POST', endpoint='/reset_timers', status='error').inc()
                TIMER_ERRORS.labels(type='reset_timers').inc()
                raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
                
            REQUEST_COUNT.labels(method='POST', endpoint='/reset_timers', status='success').inc()
            ACTIVE_TIMERS.set(0)
            
            logger.info("Timers reset", correlation_id=correlation_id)
            return result
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to reset timers", correlation_id=correlation_id, error=str(e))
        TIMER_ERRORS.labels(type='reset_timers').inc()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=SERVICE_PORT,
        log_level="info",
        access_log=True
    )
