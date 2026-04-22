from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional
from sqlalchemy import select, delete, desc

from app.deps.dependencies import get_db
from app.schemas.session import SessionResponse, Session
from app.api.v1.auth import get_current_user
from app.db.models import User
from app.db.models import SessionModel

class SessionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_sessions(self, user_id: UUID) -> list[SessionModel]:
        query = select(SessionModel).order_by(desc(SessionModel.updated_at))
        if user_id:
            query = query.where(SessionModel.user_id == user_id)
        
        result = await self.db.execute(query)
        sessions = result.scalars().all()
        return list(sessions)

    async def create_session(self, user_id: UUID, title: Optional[str] = None) -> SessionModel:
        session = SessionModel(title=title or "New Chat", user_id=user_id)
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def delete_session(self, session_id: UUID, user_id: UUID):
        query = select(SessionModel).where(SessionModel.id == session_id, SessionModel.user_id == user_id)
        result = await self.db.execute(query)
        session = result.scalar_one_or_none()
        
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        
        await self.db.delete(session)
        await self.db.commit()

    async def update_session(self, session_id: UUID, user_id: UUID, title: str) -> SessionModel:
        query = select(SessionModel).where(SessionModel.id == session_id, SessionModel.user_id == user_id)
        result = await self.db.execute(query)
        session = result.scalar_one_or_none()
        
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        
        session.title = title
        await self.db.commit()
        await self.db.refresh(session)
        return session


router = APIRouter(
    dependencies=[Depends(get_current_user), Depends(get_db)]
)

@router.get("", response_model=list[SessionResponse], status_code=status.HTTP_200_OK)
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = SessionService(db)
    return await service.get_sessions(current_user.id)

@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: Session,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = SessionService(db)
    return await service.create_session(user_id=current_user.id, title=payload.title)

@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = SessionService(db)
    await service.delete_session(session_id, current_user.id)
    return None

@router.patch("/{session_id}", response_model=SessionResponse, status_code=status.HTTP_200_OK)
async def update_session(
    session_id: UUID,
    payload: Session,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = SessionService(db)
    return await service.update_session(session_id, current_user.id, title=payload.title)