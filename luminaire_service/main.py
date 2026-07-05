import asyncio
import os
import uvicorn
import structlog
from app_logging.logging_config import configure_logging
from app_logging.require_env import require_env

from api.api_server import createAPI
from tcp.tcp_server import TCPServer
from services.luminaire_service import LuminaireService

configure_logging()
log = structlog.get_logger()

def parse_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name, "").lower()
    if value == "": return default
    return value in ("1", "true", "yes", "on")

def parse_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value: return default
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"invalid integer env var: {name}") from exc

async def startFastAPI(app):
    config = uvicorn.Config(
        app,
        host=require_env("LUMINAIRE_API_HOST"),
        port=int(require_env("LUMINAIRE_API_PORT")),
        loop=require_env("LUMINAIRE_API_LOOP"),
        log_level=require_env("LUMINAIRE_API_LOG_LEVEL"),
        access_log=parse_bool_env("LUMINAIRE_API_ACCESS_LOG", False),
    )
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    log.info("application_startup_initiated")
    
    try:
        service = LuminaireService(
            require_env("REDIS_URL"),
            require_env("LUMINAIRE_REDIS_PUB")
        )

        tcp_server = TCPServer(
            host=require_env("LUMINAIRE_TCP_HOST"),
            port=int(require_env("LUMINAIRE_TCP_PORT")),
            service=service,
            keepalive_enabled=parse_bool_env("LUMINAIRE_TCP_KEEPALIVE_ENABLED", True),
            keepalive_idle_s=parse_int_env("LUMINAIRE_TCP_KEEPALIVE_IDLE_S", 5),
            keepalive_interval_s=parse_int_env("LUMINAIRE_TCP_KEEPALIVE_INTERVAL_S", 2),
            keepalive_count=parse_int_env("LUMINAIRE_TCP_KEEPALIVE_COUNT", 3),
            tcp_user_timeout_ms=parse_int_env("LUMINAIRE_TCP_USER_TIMEOUT_MS", 3000),
        )

        app = createAPI(service)

        log.info("servers_starting", mode="production" if os.getenv("APP_ENV") == "production" else "dev")
        
        await asyncio.gather(
            tcp_server.start(),
            startFastAPI(app)
        )
    except Exception as e:
        log.critical("application_startup_failed", error=str(e), exc_info=True)
    finally:
        log.info("shutdown_sequence_started")
        # Ensure resources are cleaned up
        if 'tcp_server' in locals(): await tcp_server.stop()
        if 'service' in locals(): await service.shutdown()
        log.info("shutdown_complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass