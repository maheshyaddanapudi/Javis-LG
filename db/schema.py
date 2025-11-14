"""
Database schema for multi-agent system.
Supports both SQLite (dev) and PostgreSQL (prod).
"""

from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

Base = declarative_base()


class ExecutionPlanDB(Base):
    """Stores execution plans with versioning."""
    __tablename__ = "execution_plans"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(String(36), index=True, nullable=False)
    conversation_id = Column(String(36), index=True, nullable=False)
    plan_data = Column(JSON, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ConversationHistory(Base):
    """Stores complete conversation history."""
    __tablename__ = "conversation_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(36), index=True, nullable=False)
    message_role = Column(String(20), nullable=False)  # user, assistant, system
    message_content = Column(Text, nullable=False)
    message_data = Column(JSON)  # Full message with metadata
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)


class WorkerExecution(Base):
    """Audit trail of worker executions."""
    __tablename__ = "worker_executions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_id = Column(String(36), index=True, nullable=False)
    plan_id = Column(String(36), index=True)
    conversation_id = Column(String(36), index=True, nullable=False)
    step_id = Column(String(36))
    worker_name = Column(String(100), nullable=False)
    input_data = Column(JSON)
    output_data = Column(JSON)
    status = Column(String(20), nullable=False)  # pending, running, completed, failed
    error_message = Column(Text)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


def get_database_url() -> str:
    """
    Get database URL based on environment.
    Falls back to SQLite in dev mode.
    """
    env = os.getenv("ENVIRONMENT", "dev")
    
    if env == "prod":
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL required in production mode")
        return db_url
    else:
        # Development mode - use SQLite
        return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./agent_dev.db")


def get_sync_database_url() -> str:
    """Get synchronous database URL (for initial setup)."""
    url = get_database_url()
    # Convert async drivers to sync for initial creation
    return url.replace("+asyncpg", "").replace("+aiosqlite", "")


# Database engine factory
_engine = None
_async_session_maker = None


def get_engine():
    """Get or create database engine."""
    global _engine
    if _engine is None:
        db_url = get_database_url()
        _engine = create_async_engine(
            db_url,
            echo=os.getenv("LOG_LEVEL") == "DEBUG",
            pool_pre_ping=True,
        )
    return _engine


def get_session_maker():
    """Get or create async session maker."""
    global _async_session_maker
    if _async_session_maker is None:
        engine = get_engine()
        _async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    return _async_session_maker


async def get_db_session():
    """Get database session (async context manager)."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_database():
    """Initialize database tables."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ Database tables created/verified")


async def cleanup_database():
    """Cleanup database connections."""
    global _engine, _async_session_maker
    if _engine:
        await _engine.dispose()
        _engine = None
        _async_session_maker = None
