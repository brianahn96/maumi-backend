from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from sqlalchemy import select
import json
from datetime import datetime, timezone
from fastapi.responses import StreamingResponse

from app.deps.dependencies import get_db
from app.api.v1.auth import get_current_user
from app.schemas.chat import MessageResponse, ChatRequest
from app.db.models import MessageModel, SessionModel, MessageRole, User
from app.services.chatbot_chain import chat_graph

class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_messages(self, session_id: UUID) -> list[MessageModel]:
        query = select(MessageModel).where(MessageModel.session_id == session_id).order_by(MessageModel.created_at)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_recent_messages(self, session_id: UUID, limit: int = 5) -> list[MessageModel]:
        query = (
            select(MessageModel)
            .where(MessageModel.session_id == session_id)
            .order_by(MessageModel.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        messages = list(result.scalars().all())
        return messages[::-1]

    async def save_message(self, session_id: UUID, role: MessageRole, content: str):
        message = MessageModel(session_id=session_id, role=role, content=content)
        self.db.add(message)
        
        query = select(SessionModel).where(SessionModel.id == session_id)
        result = await self.db.execute(query)
        session = result.scalar_one_or_none()
        session.updated_at = datetime.now(timezone.utc)
        
        if role == MessageRole.user:
            if session and (session.title == "New Chat" or not session.title):
                session.title = content[:30] + "..." if len(content) > 30 else content
        
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(message)
        await self.db.refresh(session)

router = APIRouter(
    dependencies=[Depends(get_db), Depends(get_current_user)]
)

@router.get("/{session_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    service = ChatService(db)
    return await service.get_messages(session_id)

@router.post("/{session_id}/generate")
async def generate_chat(
    session_id: UUID,
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    chat_service = ChatService(db)
    
    config = {"configurable": {"thread_id": str(session_id)}}
    
    recent_messages = await chat_service.get_recent_messages(session_id, limit=5)
    
    messages = [(msg.role.value, msg.content) for msg in recent_messages]
    
    messages.append(("user", payload.message))

    await chat_service.save_message(session_id, MessageRole.user, payload.message)
    
    result = await chat_graph.ainvoke({"messages": messages, "session_id": str(session_id)}, config)
    
    await chat_service.save_message(session_id, MessageRole.assistant, result["messages"][-1].content)
    
    return {"response": result["messages"][-1].content}

@router.post("/{session_id}/stream")
async def stream_chat(
    session_id: UUID,
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    chat_service = ChatService(db)

    async def event_generator():
        full_content = ""
        config = {"configurable": {"thread_id": str(session_id)}}

        try:
            recent_messages = await chat_service.get_recent_messages(session_id, limit=5)
            messages = [(msg.role.value, msg.content) for msg in recent_messages]
            messages.append(("user", payload.message))

            async for event in chat_graph.astream_events(
                {"messages": messages, "session_id": str(session_id)},
                config,
                version="v2"
            ):
                kind = event["event"]

                if kind == "on_chat_model_stream":
                    content = event["data"]["chunk"].content
                    if content:
                        full_content += content
                        yield f"data: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"

            if full_content:
                await chat_service.save_message(session_id, MessageRole.user, payload.message)
                await chat_service.save_message(session_id, MessageRole.assistant, full_content)

            yield f"data: {json.dumps({'event': 'done'}, ensure_ascii=False)}\n\n"

        except Exception as e:
            error_msg = f"Error during streaming: {str(e)}"
            yield f"data: {json.dumps({'error': error_msg}, ensure_ascii=False)}\n\n"

    return StreamingResponse(

        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
