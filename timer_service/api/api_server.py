from fastapi import FastAPI

def createAPI():
    app = FastAPI(title="Timer Service")

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "service": "timer_service"}

    return app
