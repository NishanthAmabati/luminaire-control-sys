from fastapi import FastAPI

def createAPI():
    app = FastAPI(title="Metrics Service")

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "service": "metrics_service"}

    return app
