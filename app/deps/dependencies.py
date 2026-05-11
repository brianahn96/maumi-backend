from fastapi import Request
from typing import AsyncGenerator, Callable
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from app.db.database import PostgresManager
from app.db.redis import RedisManager    

def get_redis_manager() -> Callable[[Request], redis.Redis]:
    def _get_redis_manager(request: Request):
        manager: RedisManager = request.app.state.redis_manager
        return manager.get_client()
    return _get_redis_manager

async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    manager: PostgresManager = request.app.state.db_manager
    async with manager.session_maker() as session:
        try:
            yield session
        finally:
            await session.close()