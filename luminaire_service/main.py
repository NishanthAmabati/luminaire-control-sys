import asyncio
import logging
import os
import uvicorn
import traceback
from pythonjsonlogger import jsonlogger

from api.api_server import createAPI
from tcp.tcp_server import TCPServer
from services.luminaire_service import LuminaireService

# 1. configure json logging for docker/loki
log_handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    '%(levelname)s %(name)s %(message)s %(asctime)s'
)
log_handler.setFormatter(formatter)

root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(log_handler)

log = logging.getLogger("main")

def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        log.error(f"missing required env var {name}")
        raise RuntimeError(f"missing required env var {name}")
    return value

def parse_bool(value: str) -> bool:
    return value.lower() in ("1", "true", "yes", "on")

def parse_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if not value:
        return default
    return parse_bool(value)

def parse_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        parsed = int(value)
        if parsed < 0:
            raise ValueError
        return parsed
    except ValueError:
        log.error(f"invalid integer env var {name}")
        raise RuntimeError(f"invalid integer env var {name}")

async def start_fastapi(app):
    try:
        config = uvicorn.Config(
            app,
            host=require_env("LUMINAIRE_API_HOST"),
            port=int(require_env("LUMINAIRE_API_PORT")),
            loop=require_env("LUMINAIRE_API_LOOP"),
            log_level=require_env("LUMINAIRE_API_LOG_LEVEL").lower(),
            access_log=parse_bool(os.getenv("LUMINAIRE_API_ACCESS_LOG", "false")),
        )
        server = uvicorn.Server(config)
        log.info("starting fastapi server")
        await server.serve()
    except Exception:
        log.exception("critical failure in fastapi server")
        raise

async def main():
    log.info("initializing luminaire service architecture")
    
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

        log.info("entering main execution loop")
        await asyncio.gather(
            tcp_server.start(),
            start_fastapi(app)
        )
        
    except (asyncio.CancelledError, KeyboardInterrupt):
        log.info("shutdown requested by user or system")
    except Exception:
        log.exception("unhandled exception in main loop")
    finally:
        log.info("running cleanup and resource teardown")
        # stop tcp first to stop new connections
        try:
            await tcp_server.stop()
        except NameError:
            pass 
        
        # shutdown service (redis + active luminaires)
        try:
            await service.shutdown()
        except NameError:
            pass
            
        log.info("shutdown process complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        # final fallback for absolute startup failures
        print(f"fatal error {str(e).lower()}")