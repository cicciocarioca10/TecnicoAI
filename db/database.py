from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, select, delete, event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite+aiosqlite:///./tecnicoai.db"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

Base = declarative_base()


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, default="Nuova conversazione")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"))
    role = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    image_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Schema(Base):
    __tablename__ = "schemas"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"))
    schema_type = Column(String(50), nullable=False, default="auto")
    engine = Column(String(20), nullable=False)
    dot_code = Column(Text, nullable=True)
    svg_content = Column(Text, nullable=True)
    pdf_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def create_conversation(db: AsyncSession, title: str = "Nuova conversazione") -> Conversation:
    conv = Conversation(title=title)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def get_conversation(db: AsyncSession, conversation_id: int) -> Optional[Conversation]:
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    return result.scalar_one_or_none()


async def list_conversations(db: AsyncSession) -> list[Conversation]:
    result = await db.execute(select(Conversation).order_by(Conversation.updated_at.desc()))
    return list(result.scalars().all())


async def delete_conversation(db: AsyncSession, conversation_id: int):
    await db.execute(delete(Message).where(Message.conversation_id == conversation_id))
    await db.execute(delete(Conversation).where(Conversation.id == conversation_id))
    await db.commit()


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
