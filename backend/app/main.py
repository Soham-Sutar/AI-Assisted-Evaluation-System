import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import check_db_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("evalai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.PROJECT_NAME} in {settings.APP_ENV} mode...")
    db_ok = check_db_connection()
    if db_ok:
        logger.info("Database connection established successfully.")
    else:
        logger.warning("Database connection could not be established on startup.")
    yield
    logger.info(f"Shutting down {settings.PROJECT_NAME}...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    description="AI-Based Modular Answer Sheet Evaluation System with Bias Detection",
    lifespan=lifespan,
)

if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/", tags=["Root"])
def read_root():
    return {
        "name": settings.PROJECT_NAME,
        "version": "0.1.0",
        "status": "online",
        "docs_url": "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    db_connected = check_db_connection()
    health_status = "healthy" if db_connected else "degraded"
    return {
        "status": health_status,
        "environment": settings.APP_ENV,
        "database": "connected" if db_connected else "disconnected",
    }
