from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.db.database import PostgresManager
from app.core.config import config
from app.db.redis import RedisManager

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_manager = PostgresManager(
        url=config.postgres_aconnection_string
    )
    
    app.state.redis_manager = RedisManager(
        url=config.redis_connection_string,
        is_production=config.ENVIRONMENT == "production"
    )
    
    await app.state.redis_manager.connect()
    
    app.state.db_manager.connect()
    
    yield

    await app.state.db_manager.close()
    await app.state.redis_manager.close()
