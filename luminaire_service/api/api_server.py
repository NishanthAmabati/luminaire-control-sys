import os
import structlog
from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from models.requests import LuminaireControlRequest

log = structlog.get_logger()

def createAPI(luminaire_service):
    app = FastAPI(title="Luminaire Control API")

    cors_origins_raw = os.getenv('CORS_ORIGINS', '')
    cors_origins = [origin.strip() for origin in cors_origins_raw.split(',') if origin.strip()]
    if not cors_origins:
        cors_origins = [
            'http://localhost',
            'http://127.0.0.1',
            'http://localhost:8080',
            'http://127.0.0.1:8080',
        ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=['*'],
        allow_headers=['*'],
    )

    log.info("cors_configured", origins=cors_origins)

    @app.options("/{path:path}")
    async def preflight_handler(path: str):
        return Response(status_code=204)

    @app.get("/health")
    async def health_alias():
        try:
            health = await luminaire_service.health()
            return health
        except Exception:
            log.error("api_health_check_failed", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error during health check")

    @app.get("/devices/luminaires")
    async def get_luminaires():
        try:
            res = await luminaire_service.list_luminaires()
            return {
                "status": "ok",
                "data": res
            }
        except Exception:
            log.error("api_get_luminaires_failed", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to retrieve luminaires")

    @app.post("/devices/luminaires/set")
    async def send(req: LuminaireControlRequest):
        try:
            await luminaire_service.send_luminaires(req.cw, req.ww)
            return {"status": "ok"}
        except Exception:
            log.error("api_broadcast_failed", cw=req.cw, ww=req.ww, exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to broadcast to luminaires")

    @app.post("/devices/luminaire/send/{ip}")
    async def send_luminaire(ip: str, command: str):
        try:
            await luminaire_service.send_luminaire(ip, command)
            return {"status": "ok"}
        except Exception:
            log.error("api_send_single_failed", target_ip=ip, command=command, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to send command to {ip}")

    @app.post("/devices/luminaires/disconnect/{ip}")
    async def disconnect_luminaire(ip: str):
        try:
            await luminaire_service.unregister(ip)
            return {"status": "ok"}
        except Exception:
            log.error("api_disconnect_failed", target_ip=ip, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to disconnect {ip}")

    return app