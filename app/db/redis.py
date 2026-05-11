from dataclasses import dataclass, field
import redis.asyncio as redis

@dataclass
class RedisManager:
    url: str
    is_production: bool = False

    _client: redis.Redis = field(default_factory=lambda: None)

    def connect(self) -> redis.Redis:
        self._client = redis.from_url(
            self.url,
            db=0,
            max_connections=20,
            decode_responses=True,
        )
        return self._client

    async def close(self) -> None:
        await self._client.close()

    def get_client(self) -> redis.Redis:
        return self._client