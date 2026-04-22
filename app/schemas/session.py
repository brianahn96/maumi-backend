from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional

class Session(BaseModel):
    title: Optional[str] = None

class SessionResponse(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class SessionsListResponse(BaseModel):
    sessions: list[SessionResponse]
