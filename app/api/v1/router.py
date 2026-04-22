from fastapi import APIRouter
from app.api.v1 import auth
from app.api.v1.endpoints import chat, sessions

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])