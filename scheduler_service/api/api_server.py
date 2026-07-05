from fastapi import FastAPI

def createAPI():
    app = FastAPI(title="Scheduler Service")

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "service": "scheduler_service"}

    return app
