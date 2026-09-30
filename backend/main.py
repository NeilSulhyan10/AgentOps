from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import structlog

from backend.config import settings
from backend.api.routes import router, investigation_router
from backend.services.investigation_service import investigation_service
from backend.services.mongodb import mongodb


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AgentOps backend", env=settings.app_env)
    await mongodb.connect()
    logger.info("MongoDB connected")
    yield
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