import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func, select, delete, event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./tecnicoai.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    title = Column(String(255), nullable=False, default="Nuova conversazione")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"))
    role = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    image_path = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Schema(Base):
    __tablename__ = "schemas"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"))
    schema_type = Column(String(50), nullable=False, default="auto")
    engine = Column(String(20), nullable=False)
    dot_code = Column(Text, nullable=True)
    svg_content = Column(Text, nullable=True)
    pdf_path = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# ─── USER ────────────────────────────────────────────────────────────────────

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    email: str,
    password_hash: str,
    full_name: str,
    is_admin: bool = False,
) -> User:
    user = User(email=email, password_hash=password_hash, full_name=full_name, is_admin=is_admin)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def count_users(db: AsyncSession) -> int:
    result = await db.execute(select(func.count()).select_from(User))
    return result.scalar_one()


# ─── CONVERSATION ─────────────────────────────────────────────────────────────

async def create_conversation(
    db: AsyncSession,
    title: str = "Nuova conversazione",
    user_id: Optional[int] = None,
) -> Conversation:
    conv = Conversation(title=title, user_id=user_id)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def get_conversation(db: AsyncSession, conversation_id: int) -> Optional[Conversation]:
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    return result.scalar_one_or_none()


async def list_conversations(db: AsyncSession, user_id: Optional[int] = None) -> list[Conversation]:
    q = select(Conversation)
    if user_id is not None:
        q = q.where(Conversation.user_id == user_id)
    q = q.order_by(Conversation.updated_at.desc())
    result = await db.execute(q)
    return list(result.scalars().all())


async def delete_conversation(db: AsyncSession, conversation_id: int):
    schemas_result = await db.execute(
        select(Schema).where(Schema.conversation_id == conversation_id)
    )
    for schema in schemas_result.scalars().all():
        if schema.pdf_path and os.path.isfile(schema.pdf_path):
            try:
                os.unlink(schema.pdf_path)
            except OSError:
                pass
    await db.execute(delete(Schema).where(Schema.conversation_id == conversation_id))
    await db.execute(delete(Message).where(Message.conversation_id == conversation_id))
    await db.execute(delete(Conversation).where(Conversation.id == conversation_id))
    await db.commit()


# ─── MESSAGE ──────────────────────────────────────────────────────────────────

async def create_message(
    db: AsyncSession,
    conversation_id: int,
    role: str,
    content: str,
    image_path: Optional[str] = None,
) -> Message:
    msg = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        image_path=image_path,
    )
    db.add(msg)
    await db.execute(
        Conversation.__table__.update()
        .where(Conversation.id == conversation_id)
        .values(updated_at=datetime.now(timezone.utc))
    )
    await db.commit()
    await db.refresh(msg)
    return msg


async def get_messages(db: AsyncSession, conversation_id: int) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    return list(result.scalars().all())


# ─── SCHEMA ──────────────────────────────────────────────────────────────────

async def create_schema(
    db: AsyncSession,
    conversation_id: int,
    schema_type: str,
    engine: str,
    dot_code: Optional[str] = None,
    svg_content: Optional[str] = None,
    pdf_path: Optional[str] = None,
) -> Schema:
    schema = Schema(
        conversation_id=conversation_id,
        schema_type=schema_type,
        engine=engine,
        dot_code=dot_code,
        svg_content=svg_content,
        pdf_path=pdf_path,
    )
    db.add(schema)
    await db.commit()
    await db.refresh(schema)
    return schema


async def get_schema(db: AsyncSession, schema_id: int) -> Optional[Schema]:
    result = await db.execute(select(Schema).where(Schema.id == schema_id))
    return result.scalar_one_or_none()
