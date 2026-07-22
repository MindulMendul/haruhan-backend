from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.scheduler.jobs import shutdown_scheduler, start_scheduler


def create_app() -> FastAPI:
    app = FastAPI(title="Haruhan Backend", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.on_event("startup")
    def on_startup():
        start_scheduler()

    @app.on_event("shutdown")
    def on_shutdown():
        shutdown_scheduler()

    return app


app = create_app()
