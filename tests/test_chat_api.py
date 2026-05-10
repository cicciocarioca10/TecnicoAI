import io
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
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
async def test_create_conversation(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/api/conversations", json={"title": "Test conv"})
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test conv"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_conversations_empty(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/conversations")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_delete_conversation(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        create = await client.post("/api/conversations", json={"title": "Da eliminare"})
        conv_id = create.json()["id"]
        response = await client.delete(f"/api/conversations/{conv_id}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_nonexistent_conversation(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.delete("/api/conversations/9999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_chat_creates_messages(test_app):
    with patch("api.chat.send_message", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = "Certo! Prima di procedere, qual è la tensione di rete?"
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            create = await client.post("/api/conversations", json={"title": "Test chat"})
            conv_id = create.json()["id"]
            response = await client.post("/api/chat", data={
                "conversation_id": conv_id,
                "message": "Come installo un interruttore differenziale?",
                "model": "claude",
            })
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert data["reply"] == "Certo! Prima di procedere, qual è la tensione di rete?"


@pytest.mark.asyncio
async def test_get_conversation_messages(test_app):
    with patch("api.chat.send_message", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = "Risposta tecnica"
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            create = await client.post("/api/conversations", json={"title": "History test"})
            conv_id = create.json()["id"]
            await client.post("/api/chat", data={
                "conversation_id": conv_id,
                "message": "Ciao",
                "model": "claude",
            })
            response = await client.get(f"/api/conversations/{conv_id}/messages")
    assert response.status_code == 200
    messages = response.json()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_chat_messages_persisted(test_app):
    with patch("api.chat.send_message", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = "Perfetto, grazie."
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            create = await client.post("/api/conversations", json={"title": "Persist test"})
            conv_id = create.json()["id"]
            await client.post("/api/chat", data={
                "conversation_id": conv_id,
                "message": "Come si installa un cavo?",
                "model": "claude",
            })
            msgs = await client.get(f"/api/conversations/{conv_id}/messages")
    assert len(msgs.json()) == 2
    assert msgs.json()[0]["content"] == "Come si installa un cavo?"
    assert msgs.json()[1]["content"] == "Perfetto, grazie."


@pytest.mark.asyncio
async def test_chat_ai_failure_returns_502(test_app):
    with patch("api.chat.send_message", new_callable=AsyncMock) as mock_ai:
        mock_ai.side_effect = RuntimeError("AI down")
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            create = await client.post("/api/conversations", json={"title": "Error test"})
            conv_id = create.json()["id"]
            response = await client.post("/api/chat", data={
                "conversation_id": conv_id,
                "message": "Ciao",
                "model": "claude",
            })
    assert response.status_code == 502


@pytest.mark.asyncio
async def test_get_messages_nonexistent_conversation(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/conversations/9999/messages")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_chat_with_image(test_app):
    with patch("api.chat.send_message", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = "Vedo un interruttore magnetotermico."
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            create = await client.post("/api/conversations", json={"title": "Image test"})
            conv_id = create.json()["id"]
            response = await client.post(
                "/api/chat",
                data={"conversation_id": conv_id, "message": "Cosa vedi?", "model": "claude"},
                files={"image": ("test.jpg", b"\xff\xd8\xff\xe0fake", "image/jpeg")},
            )
    assert response.status_code == 200
    assert response.json()["reply"] == "Vedo un interruttore magnetotermico."
    call_kwargs = mock_ai.call_args.kwargs
    assert call_kwargs["image_base64"] is not None
    assert call_kwargs["image_type"] == "image/jpeg"


@pytest.mark.asyncio
async def test_chat_invalid_model(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        create = await client.post("/api/conversations", json={"title": "Model test"})
        conv_id = create.json()["id"]
        response = await client.post("/api/chat", data={
            "conversation_id": conv_id,
            "message": "Ciao",
            "model": "gpt-9",
        })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_upload_not_found(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/uploads/nonexistent_file_xyz.jpg")
    assert response.status_code == 404
