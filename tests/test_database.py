import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from db.database import Base, create_conversation, get_conversation, list_conversations, delete_conversation, create_message, get_messages


TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_conversation(db_session):
    conv = await create_conversation(db_session, "Test impianto elettrico")
    assert conv.id is not None
    assert conv.title == "Test impianto elettrico"
    assert conv.created_at is not None


@pytest.mark.asyncio
async def test_list_conversations(db_session):
    await create_conversation(db_session, "Conv 1")
    await create_conversation(db_session, "Conv 2")
    convs = await list_conversations(db_session)
    assert len(convs) == 2


@pytest.mark.asyncio
async def test_get_conversation(db_session):
    conv = await create_conversation(db_session, "Test")
    fetched = await get_conversation(db_session, conv.id)
    assert fetched.id == conv.id
    assert fetched.title == "Test"


@pytest.mark.asyncio
async def test_delete_conversation(db_session):
    conv = await create_conversation(db_session, "Da eliminare")
    await delete_conversation(db_session, conv.id)
    result = await get_conversation(db_session, conv.id)
    assert result is None


@pytest.mark.asyncio
async def test_create_and_get_messages(db_session):
    conv = await create_conversation(db_session, "Chat test")
    msg = await create_message(db_session, conv.id, "user", "Come installo un interruttore?")
    assert msg.id is not None
    assert msg.role == "user"
    messages = await get_messages(db_session, conv.id)
    assert len(messages) == 1
    assert messages[0].content == "Come installo un interruttore?"


@pytest.mark.asyncio
async def test_messages_deleted_with_conversation(db_session):
    conv = await create_conversation(db_session, "Conv con messaggi")
    await create_message(db_session, conv.id, "user", "Domanda")
    await delete_conversation(db_session, conv.id)
    messages = await get_messages(db_session, conv.id)
    assert len(messages) == 0


@pytest.mark.asyncio
async def test_list_conversations_ordered_by_updated_at(db_session):
    conv1 = await create_conversation(db_session, "First")
    conv2 = await create_conversation(db_session, "Second")
    # Send a message to conv1 to bump its updated_at after conv2's
    import asyncio
    await asyncio.sleep(0.01)
    await create_message(db_session, conv1.id, "user", "Bump")
    convs = await list_conversations(db_session)
    assert convs[0].id == conv1.id  # conv1 most recently updated


@pytest.mark.asyncio
async def test_get_nonexistent_conversation_returns_none(db_session):
    result = await get_conversation(db_session, 99999)
    assert result is None
