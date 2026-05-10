import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from db.database import Base, create_conversation, create_schema, get_schema

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_schema_svg(db_session):
    conv = await create_conversation(db_session, "Test")
    schema = await create_schema(
        db_session,
        conversation_id=conv.id,
        schema_type="auto",
        engine="svg",
        svg_content="<svg/>",
        pdf_path="schemas/test.pdf",
    )
    assert schema.id is not None
    assert schema.engine == "svg"
    assert schema.dot_code is None


@pytest.mark.asyncio
async def test_create_schema_graphviz(db_session):
    conv = await create_conversation(db_session, "Test")
    schema = await create_schema(
        db_session,
        conversation_id=conv.id,
        schema_type="plc",
        engine="graphviz",
        dot_code="digraph { A -> B }",
        pdf_path="schemas/test.pdf",
    )
    assert schema.engine == "graphviz"
    assert schema.svg_content is None


@pytest.mark.asyncio
async def test_get_schema_returns_none_for_missing(db_session):
    result = await get_schema(db_session, 9999)
    assert result is None


@pytest.mark.asyncio
async def test_get_schema_returns_created(db_session):
    conv = await create_conversation(db_session, "Test")
    created = await create_schema(
        db_session,
        conversation_id=conv.id,
        schema_type="auto",
        engine="svg",
        pdf_path="schemas/x.pdf",
    )
    fetched = await get_schema(db_session, created.id)
    assert fetched is not None
    assert fetched.id == created.id
