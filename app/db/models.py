from sqlalchemy import (
    Column, 
    String, 
    DateTime, 
    Boolean,
    ForeignKey,
    Text,
    Enum as SQLAlchemyEnum,
)
from typing import Literal
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import UUID
from enum import Enum
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.core.utils import uuid7_generator

class AuthProvider(Enum):
    local = "local"
    google = "google"
    kakao = "kakao"
    naver = "naver"
    
class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7_generator)
    email = Column(String, nullable=False, index=True, unique=True)
    is_active = Column(Boolean, default=True)
    
    # Authentication fields
    provider = Column(SQLAlchemyEnum(AuthProvider), nullable=False)
    provider_user_id = Column(String, nullable=True, unique=True)  # Nullable for local auth
    hashed_password = Column(String, nullable=True)   # Nullable for OAuth
    avatar_url = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_login_at = Column(DateTime(timezone=True), nullable=True)

class SessionModel(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7_generator)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False, default="New Chat")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    messages = relationship("MessageModel", back_populates="session", cascade="all, delete-orphan")

class MessageRole(Enum):
    user = "user"
    assistant = "assistant"

class MessageModel(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid7_generator)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(SQLAlchemyEnum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    session = relationship("SessionModel", back_populates="messages")
