import os
import structlog

from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models.requests import *
from services.state_service import StateService

log = structlog.get_logger()

def createAPI(state_service: StateService) -> FastAPI:
    app = FastAPI(title='State Service')

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

    @app.on_event('startup')
    async def startup():
        log.info("api_startup_hook_triggered")
        try:
            await state_service.load()
        except Exception as e:
            log.error("api_startup_state_load_failed", error=str(e), exc_info=True)

    @app.get('/state')
    async def get_state():
        try:
            state = await state_service.get_state()
            return state.to_dict()
        except Exception as e:
            log.error("api_get_state_failed", error=str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error retrieving state")

    @app.post('/system/power')
    async def set_system_power(req: SystemPowerRequest):
        try:
            await state_service.set_system_power(req.on)
            return {'status': 'ok', 'system_on': req.on}
        except Exception as e:
            log.error("api_set_power_failed", system_on=req.on, error=str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to toggle system power")

    @app.post('/system/mode')
    async def set_mode(req: ModeRequest):
        try:
            await state_service.set_mode(req.mode)
            return {'status': 'ok', 'mode': req.mode}
        except Exception as e:
            log.error("api_set_mode_failed", mode=req.mode, error=str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to set system mode")

    @app.post('/timer/toggle')
    async def toggle_timer(enabled: bool):
        try:
            await state_service.toggle_timer(enabled)
            return {'status': 'ok', 'timer': {'enabled': enabled}}
        except Exception as e:
            log.error("api_toggle_timer_failed", enabled=enabled, error=str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to toggle timer")

    @app.post('/timer/configure')
    async def configure_timer(req: TimerConfigureRequest):
        try:
            await state_service.configure_timer(req.start, req.end)
            return {'status': 'ok', 'timer': {'start': req.start, 'end': req.end}}
        except Exception as e:
            log.error("api_configure_timer_failed", start=req.start, end=req.end, error=str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to configure timer")

    @app.get('/timer/clear')
    async def clear_timer():
        try:
            await state_service.clear_timer()
            return {'status': 'ok'}
        except Exception as e:
            log.error("api_clear_timer_failed", error=str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to clear timer")

    @app.post('/scene/load')
    async def load_scene(req: SceneRequest):
        try:
            await state_service.load_scene(req.scene)
            return {'status': 'ok', 'loaded_scene': req.scene}
        except Exception as e:
            log.error("api_load_scene_failed", scene=req.scene, error=str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to load scene")

    @app.post('/scene/activate')
    async def activate_scene(req: SceneRequest):
        try:
            await state_service.activate_scene(req.scene)
            return {'status': 'ok', 'running_scene': req.scene}
        except Exception as e:
            log.error("api_activate_scene_failed", scene=req.scene, error=str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to activate scene")

    @app.post('/scene/deactivate')
    async def deactivate_scene(req: SceneRequest):
        try:
            await state_service.deactivate_scene(req.scene)
            return {'status': 'ok'}
        except Exception as e:
            log.error("api_deactivate_scene_failed", scene=req.scene, error=str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to deactivate scene")

    @app.get('/scene/available')
    async def refresh_available_scenes():
        try:
            await state_service.request_available_scenes()
            return {'status': 'ok'}
        except Exception as e:
            log.error("api_refresh_scenes_failed", error=str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to request available scenes")

    @app.post('/set/manual')
    async def set_manual_values(req: ManualRequest):
        if req.medium == "sliders":
            if req.cct is None or req.lux is None:
                log.warning("api_manual_set_rejected", reason="missing_cct_lux", medium=req.medium)
                raise HTTPException(status_code=400, detail="cct and lux are required for sliders mode")
        elif req.medium == "buttons":
            if req.cw is None or req.ww is None:
                log.warning("api_manual_set_rejected", reason="missing_cw_ww", medium=req.medium)
                raise HTTPException(status_code=400, detail="cw and ww are required for buttons mode")

        try:
            await state_service.set_manual_values(
                medium=req.medium,
                cct=req.cct,
                lux=req.lux,
                cw=req.cw,
                ww=req.ww,
            )
            
            if req.medium == "sliders":
                return {'status': 'ok', 'manual': {'cct': req.cct, 'lux': req.lux}}
            return {'status': 'ok', 'manual': {'cw': req.cw, 'ww': req.ww}}
            
        except Exception as e:
            log.error("api_manual_set_failed", payload=req.dict(), error=str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to set manual values")

    return app