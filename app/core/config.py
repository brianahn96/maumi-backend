from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, model_validator, field_validator
from typing import Union
from urllib.parse import quote_plus

from app.core.logger import logger

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # GOOGLE_API_KEY: SecretStr
    # GOOGLE_EMBEDDING_MODEL: str
    GROQ_API_KEY: SecretStr
    OPENROUTER_API_KEY: SecretStr
    
    SECRET_KEY: SecretStr

    REDIS_HOST: str
    REDIS_PORT: int

    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_USER: str
    POSTGRES_PASSWORD: SecretStr
    POSTGRES_DB: str

    ENVIRONMENT: str = "development"

    ALLOWED_ORIGINS: str | list[str] = []

    @property
    def postgres_aconnection_string(self) -> str:
        password = quote_plus(self.POSTGRES_PASSWORD.get_secret_value())
        
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{password}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
    
    @property
    def postgres_connection_string(self) -> str:
        password = quote_plus(self.POSTGRES_PASSWORD.get_secret_value())
        
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{password}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
        
    @property
    def redis_connection_string(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}"

    @model_validator(mode='after')
    def validate_settings(self) -> 'Settings':
        return self
    
    @field_validator("ALLOWED_ORIGINS", mode="before")
    def parse_allowed_origins(cls, v: str | list) -> list[str]:
        if isinstance(v, list):
            return v

        if v.startswith("["):
            import json
            return json.loads(v)

        return [origin.strip() for origin in v.split(",") if origin.strip()]

try:
    config = Settings()
except Exception as e:
    logger.error(f"설정 로드 중 오류 발생: {e}")
    exit(1)
