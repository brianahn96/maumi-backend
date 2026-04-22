from dataclasses import dataclass, field
from enum import Enum
import redis.asyncio as redis

class RedisDB(Enum):
    DEFAULT = 0
    AUTH = 1
    CACHE = 2

@dataclass
class RedisManager:
    url: str

    _clients: dict[RedisDB, redis.Redis] = field(
        init=False,
        default_factory=dict
    )

    def connect(self, db: RedisDB = RedisDB.DEFAULT) -> redis.Redis:
        if db not in self._clients:
            self._clients[db] = redis.from_url(
                self.url,
                db=db.value,
                max_connections=20,
                decode_responses=True,
            )
        return self._clients[db]

    async def close(self) -> None:
        for client in self._clients.values():
            await client.close()
        self._clients.clear()

    def get_client(self, db: RedisDB = RedisDB.DEFAULT) -> redis.Redis:
        if db not in self._clients:
            return self.connect(db)
        return self._clients[db]