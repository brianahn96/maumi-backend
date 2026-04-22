from dataclasses import dataclass, field
from typing import Optional
from sqlalchemy.ext.asyncio import (
    create_async_engine, 
    AsyncSession, 
    async_sessionmaker, 
    AsyncEngine
)
from sqlalchemy.orm import DeclarativeBase

@dataclass
class PostgresManager:
    url: str
    echo: bool = True
    
    _engine: Optional[AsyncEngine] = field(init=False, default=None)
    _sessionmaker: Optional[async_sessionmaker[AsyncSession]] = field(init=False, default=None)

    def connect(self) -> None:
        if self._engine is None:
            self._engine = create_async_engine(
                self.url,
                echo=self.echo,
                pool_size=15,
                max_overflow=10,
                pool_timeout=30,
                pool_recycle=900,
                pool_pre_ping=True,
            )
            self._sessionmaker = async_sessionmaker(
                bind=self._engine,
                class_=AsyncSession,
                expire_on_commit=False
            )

    async def close(self) -> None:
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._sessionmaker = None

    @property
    def session_maker(self) -> async_sessionmaker[AsyncSession]:
        if self._sessionmaker is None:
            self.connect()
        return self._sessionmaker

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            self.connect()
        return self._engine

class Base(DeclarativeBase):
    pass
