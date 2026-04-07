import os

from fastapi import FastAPI, Response, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from models.requests import *
from services.state_service import StateService
from utils.tracing import create_trace_logger, generate_trace_id

TRACE_HEADER = "x-trace-id"


def createAPI(state_service: StateService) -> FastAPI:
    app = FastAPI(title="State Service")

    cors_origins_raw = os.getenv("CORS_ORIGINS", "")
    cors_origins = [
        origin.strip() for origin in cors_origins_raw.split(",") if origin.strip()
    ]
    if not cors_origins:
        cors_origins = [
            "http://localhost",
            "http://127.0.0.1",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.options("/{path:path}")
    async def preflight_handler(path: str):
        return Response(status_code=204)

    @app.on_event("startup")
    async def startup():
        await state_service.load()

    @app.middleware("http")
    async def trace_middleware(request: Request, call_next):
        trace_id = request.headers.get(TRACE_HEADER)
        if not trace_id:
            trace_id = generate_trace_id()
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers[TRACE_HEADER.upper()] = trace_id
        return response

    @app.get("/state")
    async def get_state(request: Request):
        trace_id = getattr(request.state, "trace_id", None)
        trace_log = create_trace_logger(
            __import__("logging").getLogger("api"), trace_id
        )
        trace_log.debug("state requested")
        return (await state_service.get_state()).to_dict()

    @app.post("/system/power")
    async def set_system_power(req: SystemPowerRequest, request: Request):
        trace_id = getattr(request.state, "trace_id", None)
        trace_log = create_trace_logger(
            __import__("logging").getLogger("api"), trace_id
        )
        trace_log.info("system power request received")
        await state_service.set_system_power(req.on, trace_id=trace_id)
        return {"status": "ok", "system_on": req.on, "trace_id": trace_id}

    @app.post("/system/mode")
    async def set_mode(req: ModeRequest, request: Request):
        trace_id = getattr(request.state, "trace_id", None)
        trace_log = create_trace_logger(
            __import__("logging").getLogger("api"), trace_id
        )
        trace_log.info("mode change request received")
        await state_service.set_mode(req.mode, trace_id=trace_id)
        return {"status": "ok", "mode": req.mode, "trace_id": trace_id}

    @app.post("/timer/toggle")
    async def toggle_timer(enabled: bool, request: Request):
        trace_id = getattr(request.state, "trace_id", None)
        await state_service.toggle_timer(enabled, trace_id=trace_id)
        return {"status": "ok", "timer": {"enabled": enabled}, "trace_id": trace_id}

    @app.post("/timer/configure")
    async def configure_timer(req: TimerConfigureRequest, request: Request):
        trace_id = getattr(request.state, "trace_id", None)
        await state_service.configure_timer(req.start, req.end, trace_id=trace_id)
        return {
            "status": "ok",
            "timer": {"start": req.start, "end": req.end},
            "trace_id": trace_id,
        }

    @app.get("/timer/clear")
    async def clear_timer(request: Request):
        trace_id = getattr(request.state, "trace_id", None)
        await state_service.clear_timer(trace_id=trace_id)
        return {"status": "ok", "trace_id": trace_id}

    @app.post("/scene/load")
    async def load_scene(req: SceneRequest, request: Request):
        trace_id = getattr(request.state, "trace_id", None)
        trace_log = create_trace_logger(
            __import__("logging").getLogger("api"), trace_id
        )
        trace_log.info("load scene request received: %s", req.scene)
        await state_service.load_scene(req.scene, trace_id=trace_id)
        return {"status": "ok", "loaded_scene": req.scene, "trace_id": trace_id}

    @app.post("/scene/activate")
    async def activate_scene(req: SceneRequest, request: Request):
        trace_id = getattr(request.state, "trace_id", None)
        trace_log = create_trace_logger(
            __import__("logging").getLogger("api"), trace_id
        )
        trace_log.info("activate scene request received: %s", req.scene)
        await state_service.activate_scene(req.scene, trace_id=trace_id)
        return {"status": "ok", "running_scene": req.scene, "trace_id": trace_id}

    @app.post("/scene/deactivate")
    async def deactivate_scene(req: SceneRequest, request: Request):
        trace_id = getattr(request.state, "trace_id", None)
        trace_log = create_trace_logger(
            __import__("logging").getLogger("api"), trace_id
        )
        trace_log.info("deactivate scene request received")
        await state_service.deactivate_scene(req.scene, trace_id=trace_id)
        return {"status": "ok", "trace_id": trace_id}

    @app.get("/scene/available")
    async def refresh_available_scenes(request: Request):
        trace_id = getattr(request.state, "trace_id", None)
        await state_service.request_available_scenes(trace_id=trace_id)
        return {"status": "ok", "trace_id": trace_id}

    @app.post("/set/manual")
    async def set_manual_values(req: ManualRequest, request: Request):
        trace_id = getattr(request.state, "trace_id", None)
        trace_log = create_trace_logger(
            __import__("logging").getLogger("api"), trace_id
        )
        if req.medium == "sliders":
            if req.cct is None or req.lux is None:
                raise HTTPException(
                    status_code=400, detail="cct and lux are required for sliders mode"
                )
            trace_log.info("manual update via sliders: cct %s lux %s", req.cct, req.lux)
        elif req.medium == "buttons":
            if req.cw is None or req.ww is None:
                raise HTTPException(
                    status_code=400, detail="cw and ww are required for buttons mode"
                )
            trace_log.info("manual update via buttons: cw %s ww %s", req.cw, req.ww)
        await state_service.set_manual_values(
            medium=req.medium,
            cct=req.cct,
            lux=req.lux,
            cw=req.cw,
            ww=req.ww,
            trace_id=trace_id,
        )
        if req.medium == "sliders":
            return {
                "status": "ok",
                "manual": {"cct": req.cct, "lux": req.lux},
                "trace_id": trace_id,
            }
        return {
            "status": "ok",
            "manual": {"cw": req.cw, "ww": req.ww},
            "trace_id": trace_id,
        }

    return app
