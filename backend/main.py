from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from contextlib import asynccontextmanager
import structlog

from backend.config import settings
from backend.api.routes import router, investigation_router, scenario_router, agents_router, apps_router
from backend.services.investigation_service import investigation_service
from backend.services.mongodb import mongodb
from backend.services.github_monitor import start_github_monitor, stop_github_monitor


structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


async def _sweep_interrupted_runs() -> None:
    """At startup and then every minute, mark runs nobody is updating any more as interrupted."""
    from backend.orchestrator.state import mongo_state_manager
    while True:
        try:
            marked = await mongo_state_manager.mark_interrupted(settings.stale_run_minutes)
            if marked:
                logger.warning("Marked interrupted investigations", count=marked)
        except Exception as exc:
            logger.warning("Interrupted-run sweep failed", error=str(exc))
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AgentOps backend", env=settings.app_env)
    await mongodb.connect()
    logger.info("MongoDB connected")
    
    # Start GitHub Actions monitor
    await start_github_monitor()

    # Runs whose process died (restart, crash) would otherwise stay "running" forever.
    sweeper = asyncio.create_task(_sweep_interrupted_runs())

    yield

    sweeper.cancel()
    await stop_github_monitor()
    await mongodb.close()
    logger.info("Shutting down AgentOps backend")


app = FastAPI(
    title="AgentOps API",
    description="Adaptive Multi-Agent Intelligence for DevOps Incident Investigation",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.include_router(investigation_router, prefix="/api")
app.include_router(scenario_router, prefix="/api")
app.include_router(agents_router, prefix="/api")
app.include_router(apps_router, prefix="/api")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "agentops-backend"}


@app.get("/")
async def root():
    return {
        "service": "AgentOps",
        "version": "0.1.0",
        "description": "Adaptive Multi-Agent Intelligence for DevOps Incident Investigation",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=settings.debug
    )