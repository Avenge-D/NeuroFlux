import asyncio
import os
from typing import Optional, List
from sqlalchemy import String, Integer, DateTime, Enum, JSON
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime, timezone
import enum

from config import settings
from logger import logger

# Models
class Base(DeclarativeBase):
    pass

class TopicStatus(enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    GENERATED = "GENERATED"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"

class ContentItemStatus(enum.Enum):
    PENDING = "PENDING"
    AUDIO_GENERATED = "AUDIO_GENERATED"
    MEDIA_FETCHED = "MEDIA_FETCHED"
    RENDERED = "RENDERED"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"

class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[int] = mapped_column(primary_key=True)
    prompt: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    status: Mapped[TopicStatus] = mapped_column(Enum(TopicStatus), default=TopicStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class ContentItem(Base):
    __tablename__ = "content_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(Integer, nullable=False)
    narrative_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    audio_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    rendered_video_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[ContentItemStatus] = mapped_column(Enum(ContentItemStatus), default=ContentItemStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

# Ensure the data directory exists before SQLite tries to create the file
os.makedirs("data", exist_ok=True)

# Engine and Session initialization
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    """Initializes the database, creating tables if they don't exist."""
    async with engine.begin() as conn:
        # For production, use alembic instead of create_all
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized successfully.")

# Helper: async generator — use with `async for session in get_session()` or
# preferably use AsyncSessionLocal() as a context manager directly.
async def get_session() -> AsyncSession:
    """Async generator that yields a transactional session and closes it on exit."""
    async with AsyncSessionLocal() as session:
        yield session
