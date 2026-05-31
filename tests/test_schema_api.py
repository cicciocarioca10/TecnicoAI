import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from main import app
from db.database import Base, get_db

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def test_app():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    TestSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_generate_schema_svg(test_app):
    mock_result = {
        "schema_id": 1,
        "engine": "svg",
        "schema_type": "auto",
        "pdf_url": "/api/schema/pdf/1",
        "content": "<svg viewBox='0 0 1123 794'><rect/></svg>",
    }
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        create = await client.post("/api/conversations", json={"title": "Test"})
        conv_id = create.json()["id"]
        with patch("api.schema.schema_service.generate_schema", new_callable=AsyncMock, return_value=mock_result):
            r = await client.post("/api/schema/generate", json={"conversation_id": conv_id, "domain": "auto"})
    assert r.status_code == 200
    data = r.json()
    assert data["engine"] == "svg"
    assert data["schema_id"] == 1
    assert "content" in data


@pytest.mark.asyncio
async def test_generate_schema_plc_domain(test_app):
    mock_result = {
        "schema_id": 2,
        "engine": "svg",
        "schema_type": "plc",
        "pdf_url": "/api/schema/pdf/2",
        "content": "<svg viewBox='0 0 1123 794'><rect/></svg>",
    }
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        create = await client.post("/api/conversations", json={"title": "PLC Test"})
        conv_id = create.json()["id"]
        with patch("api.schema.schema_service.generate_schema", new_callable=AsyncMock, return_value=mock_result):
            r = await client.post("/api/schema/generate", json={"conversation_id": conv_id, "domain": "plc"})
    assert r.status_code == 200
    assert r.json()["engine"] == "svg"
    assert r.json()["schema_type"] == "plc"


@pytest.mark.asyncio
async def test_generate_schema_invalid_domain(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        create = await client.post("/api/conversations", json={"title": "Test"})
        conv_id = create.json()["id"]
        r = await client.post("/api/schema/generate", json={"conversation_id": conv_id, "domain": "invalid_xyz"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_generate_schema_conversation_not_found(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        with patch("api.schema.schema_service.generate_schema", new_callable=AsyncMock) as mock_gen:
            r = await client.post("/api/schema/generate", json={"conversation_id": 9999, "domain": "auto"})
    assert r.status_code == 404
    mock_gen.assert_not_called()


@pytest.mark.asyncio
async def test_generate_schema_invalid_model(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        create = await client.post("/api/conversations", json={"title": "Test"})
        conv_id = create.json()["id"]
        r = await client.post("/api/schema/generate", json={"conversation_id": conv_id, "domain": "auto", "model": "gpt-99"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_generate_schema_ai_error(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        create = await client.post("/api/conversations", json={"title": "Test"})
        conv_id = create.json()["id"]
        with patch("api.schema.schema_service.generate_schema", new_callable=AsyncMock, side_effect=RuntimeError("AI error")):
            r = await client.post("/api/schema/generate", json={"conversation_id": conv_id, "domain": "auto"})
    assert r.status_code == 502


@pytest.mark.asyncio
async def test_get_schema_pdf_not_found(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        r = await client.get("/api/schema/pdf/9999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_generate_all_valid_domains(test_app):
    valid_domains = ["elettrico", "plc", "pneumatico", "idraulico", "meccatronico", "fieldbus", "safety", "auto"]
    mock_result = {
        "schema_id": 1, "engine": "svg", "schema_type": "auto",
        "pdf_url": "/api/schema/pdf/1", "content": "<svg/>",
    }
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        create = await client.post("/api/conversations", json={"title": "Test"})
        conv_id = create.json()["id"]
        for domain in valid_domains:
            with patch("api.schema.schema_service.generate_schema", new_callable=AsyncMock, return_value=mock_result):
                r = await client.post("/api/schema/generate", json={"conversation_id": conv_id, "domain": domain})
            assert r.status_code == 200, f"Domain {domain} returned {r.status_code}"
