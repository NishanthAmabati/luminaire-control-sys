import os

from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models.requests import *
from services.state_service import StateService


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
        # Keep credentials disabled unless you explicitly need cookies/auth headers.
        allow_credentials=False,
        allow_methods=['*'],
        allow_headers=['*'],
    )

    # Explicit OPTIONS handler to avoid 405s on CORS preflight in some environments.
    @app.options("/{path:path}")
    async def preflight_handler(path: str):
        return Response(status_code=204)

    @app.on_event('startup')
    async def startup():
        await state_service.load()

    @app.get('/state')
    async def get_state():
        return (await state_service.get_state()).to_dict()

    @app.post('/system/power')
    async def set_system_power(req: SystemPowerRequest):
        await state_service.set_system_power(req.on)
        return {'status': 'ok', 'system_on': req.on}

    @app.post('/system/mode')
    async def set_mode(req: ModeRequest):
        await state_service.set_mode(req.mode)
        return {'status': 'ok', 'mode': req.mode}

    @app.post('/timer/toggle')
    async def toggle_timer(enabled: bool):
        await state_service.toggle_timer(enabled)
        return {'status': 'ok', 'timer': {'enabled': enabled}}

    @app.post('/timer/configure')
    async def configure_timer(req: TimerConfigureRequest):
        await state_service.configure_timer(req.start, req.end)
        return {'status': 'ok', 'timer': {'start': req.start, 'end': req.end}}

    @app.get('/timer/clear')
    async def clear_timer():
        await state_service.clear_timer()
        return {'status': 'ok'}

    @app.post('/scene/load')
    async def load_scene(req: SceneRequest):
        await state_service.load_scene(req.scene)
        return {'status': 'ok', 'loaded_scene': req.scene}

    @app.post('/scene/activate')
    async def activate_scene(req: SceneRequest):
        await state_service.activate_scene(req.scene)
        return {'status': 'ok', 'running_scene': req.scene}

    @app.post('/scene/deactivate')
    async def deactivate_scene(req: SceneRequest):
        await state_service.deactivate_scene(req.scene)
        return {'status': 'ok'}

    @app.get('/scene/available')
    async def refresh_available_scenes():
        await state_service.request_available_scenes()
        return {'status': 'ok'}

    @app.post('/set/manual')
    async def set_manual_values(req: ManualRequest):
        if req.medium == "sliders":
            if req.cct is None or req.lux is None:
                raise HTTPException(status_code=400, detail="cct and lux are required for sliders mode")
        elif req.medium == "buttons":
            if req.cw is None or req.ww is None:
                raise HTTPException(status_code=400, detail="cw and ww are required for buttons mode")
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

    return app
