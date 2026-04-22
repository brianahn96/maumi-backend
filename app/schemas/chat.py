from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class ChatRequest(BaseModel):
    message: str

class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

class MessagesListResponse(BaseModel):
    messages: list[MessageResponse]
    session_id: UUID
