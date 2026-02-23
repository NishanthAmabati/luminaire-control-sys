from models.requests import LuminaireControlRequest
from fastapi import FastAPI, HTTPException

def createAPI(luminaire_service):
    app = FastAPI()

    @app.get("/healthy")
    async def health():
        health = await luminaire_service.health()
        return health

    @app.get("/devices/luminaires")
    async def get_luminaires():
        res = await luminaire_service.list_luminaires()
        return {
            "status": "ok",
            "data": res
        }

    @app.post("/devices/luminaires/set")
    async def send(req: LuminaireControlRequest):
        await luminaire_service.send_luminaires(req.cw, req.ww)
        return {"status": "ok"}

    @app.post("/devices/lumianire/send/{ip}")
    async def send_luminaire(ip: str, command: str):
        await luminaire_service.send_luminaire(ip, command)
        return {"status": "ok"}

    @app.post("/devices/luminaires/disconnect/{ip}")
    async def diconnect_luminaire(ip: str):
        await luminaire_service.unregister(ip)
        return {"staus": "ok"}

    return app