import asyncio
import logging
import os
import uvicorn

from api.api_server import createAPI
from tcp.tcp_server import TCPServer
from services.luminaire_service import LuminaireService

logging.basicConfig(level=logging.INFO)

def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        raise RuntimeError(f"missing required env var: {name}")
    return value

def parse_bool(value: str) -> bool:
    return value.lower() in ("1", "true", "yes", "on")

def parse_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return parse_bool(value)

def parse_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise RuntimeError(f"invalid integer env var: {name}") from exc
    if parsed < 0:
        raise RuntimeError(f"invalid negative integer env var: {name}")
    return parsed

async def startFastAPI(app):
    fastAPIconfig = uvicorn.Config(
        app,
        host=require_env("LUMINAIRE_API_HOST"),
        port=int(require_env("LUMINAIRE_API_PORT")),
        loop=require_env("LUMINAIRE_API_LOOP"),
        log_level=require_env("LUMINAIRE_API_LOG_LEVEL"),
        access_log=parse_bool(os.getenv("LUMINAIRE_API_ACCESS_LOG", "false")),
    )
    server = uvicorn.Server(fastAPIconfig)
    await server.serve()

async def main():
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

    try:
        await asyncio.gather(
            tcp_server.start(),
            startFastAPI(app)
        )
    except (asyncio.CancelledError, KeyboardInterrupt):
        logging.info("shutdown requested")
    finally:
        logging.info("running cleanup...")
        await tcp_server.stop()
        await service.shutdown()
        logging.info("shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())
