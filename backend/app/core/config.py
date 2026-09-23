import os
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_ENV: str = "development"
    PROJECT_NAME: str = "EvalAI"
    API_V1_STR: str = "/api"

    # Database
    DATABASE_URL: str = "postgresql+psycopg://evalai:evalai@postgres:5432/evalai"

    # Security
    JWT_SECRET: str = "replace-with-a-development-secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Storage
    STORAGE_PATH: str = "/app/storage"
    MAX_UPLOAD_MB: int = 20

    # AI & OCR
    OCR_LANGUAGE: str = "eng"
    AI_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    AI_DEVICE: str = "cpu"
    AI_SEMANTIC_WEIGHT: float = 0.5
    AI_KEYPOINT_WEIGHT: float = 0.5

    # Review / Discrepancy Thresholds
    DISCREPANCY_ABSOLUTE_THRESHOLD: float = 2.0
    DISCREPANCY_RELATIVE_THRESHOLD: float = 0.20

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
    ]


settings = Settings()
