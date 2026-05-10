# TecnicoAI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI + SQLite chatbot backend for Italian electricians/mechanics that asks clarifying questions before answering technical queries.

**Architecture:** Single FastAPI app with async SQLite via SQLAlchemy + aiosqlite. AI layer supports Claude (Anthropic SDK) and DeepSeek (HTTP). Question engine detects technical requests and injects clarification instructions into the system prompt when no questions have been asked yet.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0 async, aiosqlite, Anthropic SDK, python-dotenv, pytest, httpx

---

## File Map

| File | Responsibility |
|------|---------------|
| `main.py` | App factory, router registration, DB init on startup |
| `db/database.py` | SQLAlchemy models, engine, session factory, CRUD functions |
| `services/question_engine.py` | `detect_technical_request()`, `has_clarifications_been_asked()`, `build_system_prompt()` |
| `services/ai_service.py` | `send_message()` — routes to Claude or DeepSeek |
| `api/chat.py` | POST /api/chat, POST /api/conversations, DELETE /api/conversations/{id} |
| `api/history.py` | GET /api/conversations, GET /api/conversations/{id}/messages |
| `requirements.txt` | Pinned dependencies |
| `.env.example` | API key template |
| `tests/test_database.py` | DB CRUD unit tests |
| `tests/test_question_engine.py` | Question detection unit tests |
| `tests/test_chat_api.py` | API endpoint integration tests (AI mocked) |

---

### Task 1: Project Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `main.py`
- Create: `db/__init__.py`, `api/__init__.py`, `services/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: Create requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.32.0
anthropic==0.40.0
sqlalchemy==2.0.36
aiosqlite==0.20.0
python-dotenv==1.0.1
requests==2.32.3
python-multipart==0.0.12
httpx==0.27.2
pytest==8.3.3
pytest-asyncio==0.24.0
```

- [ ] **Step 2: Create .env.example**

```
CLAUDE_API_KEY=your_claude_key_here
DEEPSEEK_API_KEY=your_deepseek_key_here
AI_MODEL=claude
```

- [ ] **Step 3: Create package __init__.py files**

```bash
mkdir -p db api services tests
touch db/__init__.py api/__init__.py services/__init__.py tests/__init__.py
```

- [ ] **Step 4: Create main.py skeleton**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from db.database import init_db
from api.chat import router as chat_router
from api.history import router as history_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="TecnicoAI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api")
app.include_router(history_router, prefix="/api")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```

- [ ] **Step 5: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .env.example main.py db/__init__.py api/__init__.py services/__init__.py tests/__init__.py
git commit -m "feat: project scaffold for TecnicoAI"
```

---

### Task 2: Database Layer

**Files:**
- Create: `db/database.py`
- Create: `tests/test_database.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_database.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_database.py -v
```

Expected: `ImportError` — `db.database` not found.

- [ ] **Step 3: Implement db/database.py**

```python
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, select, delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite+aiosqlite:///./tecnicoai.db"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, default="Nuova conversazione")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"))
    role = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    image_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


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
        .values(updated_at=datetime.utcnow())
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_database.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add db/database.py tests/test_database.py
git commit -m "feat: database models and CRUD functions"
```

---

### Task 3: Question Engine

**Files:**
- Create: `services/question_engine.py`
- Create: `tests/test_question_engine.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_question_engine.py`:

```python
from services.question_engine import detect_technical_request, has_clarifications_been_asked, build_system_prompt

SYSTEM_PROMPT_BASE = "Sei un assistente tecnico."


def test_detects_electrical_request():
    assert detect_technical_request("Come installo un interruttore differenziale?") is True


def test_detects_mechanical_request():
    assert detect_technical_request("Come collegare una pompa idraulica al motore?") is True


def test_ignores_generic_question():
    assert detect_technical_request("Ciao, come stai?") is False


def test_ignores_simple_greeting():
    assert detect_technical_request("Buongiorno!") is False


def test_detects_cable_section_request():
    assert detect_technical_request("Che sezione cavo uso per 10kW trifase?") is True


def test_no_clarifications_asked_empty_history():
    messages = []
    assert has_clarifications_been_asked(messages) is False


def test_no_clarifications_asked_only_user_messages():
    messages = [{"role": "user", "content": "Voglio installare un impianto."}]
    assert has_clarifications_been_asked(messages) is False


def test_clarifications_already_asked():
    messages = [
        {"role": "user", "content": "Voglio installare un impianto."},
        {"role": "assistant", "content": "Certo! Prima di rispondere: qual è la tensione di rete?"},
    ]
    assert has_clarifications_been_asked(messages) is True


def test_build_system_prompt_technical_no_clarifications():
    prompt = build_system_prompt(is_technical=True, clarifications_asked=False)
    assert "domande di chiarimento" in prompt.lower()


def test_build_system_prompt_technical_clarifications_done():
    prompt = build_system_prompt(is_technical=True, clarifications_asked=True)
    assert "domande di chiarimento" not in prompt.lower() or "fornisci" in prompt.lower()


def test_build_system_prompt_non_technical():
    prompt = build_system_prompt(is_technical=False, clarifications_asked=False)
    assert isinstance(prompt, str)
    assert len(prompt) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_question_engine.py -v
```

Expected: `ImportError` — `services.question_engine` not found.

- [ ] **Step 3: Implement services/question_engine.py**

```python
SYSTEM_PROMPT = """Sei un assistente tecnico specializzato per elettricisti e tecnici \
meccanici italiani. Conosci le normative CEI, IEC, e le best practice del settore. \
Quando ricevi una richiesta tecnica:

1. PRIMA fai 3-5 domande di chiarimento specifiche (tensione di rete, potenza stimata, \
ambiente interno/esterno/esplosivo, normativa applicabile, presenza di acqua/umidità, \
tipologia di carico)
2. POI, con le risposte, fornisci:
   - Lista completa dei componenti necessari con specifiche tecniche
   - Sezioni dei cavi (calcolate correttamente)
   - Schema di collegamento testuale passo-passo
   - Avvertenze di sicurezza e normative applicabili
   - Stima del materiale in euro (range orientativo)

Rispondi sempre in italiano. Sii preciso e professionale."""

CLARIFICATION_INSTRUCTION = """

ISTRUZIONE PRIORITARIA: Questa è una richiesta tecnica e non hai ancora fatto domande \
di chiarimento. Inizia la tua risposta con 3-5 domande di chiarimento specifiche \
(tensione di rete, potenza stimata, ambiente interno/esterno/esplosivo, normativa \
applicabile, presenza di acqua/umidità, tipologia di carico). \
Non fornire ancora la risposta tecnica dettagliata."""

TECHNICAL_KEYWORDS = [
    "impianto", "cavo", "interruttore", "fusibile", "quadro", "tensione",
    "corrente", "potenza", "motore", "pompa", "circuito", "messa a terra",
    "differenziale", "magnetotermico", "contattore", "relè", "trasformatore",
    "inverter", "variatore", "trifase", "monofase", "kw", "kva", "ampere",
    "volt", "ohm", "schema", "collegamento", "sezione", "cei", "iec",
    "installazione", "elettrico", "meccanico", "idraulico", "pneumatico",
    "compressore", "valvola", "cilindro", "attuatore", "solenoide",
    "termostato", "sensore", "plc", "automazione", "morsettiera",
    "canalina", "cavidotto", "tubazione", "scarico", "perdita di carico",
    "efficienza", "rendimento", "portata",
]


def detect_technical_request(text: str) -> bool:
    text_lower = text.lower()
    matches = sum(1 for kw in TECHNICAL_KEYWORDS if kw in text_lower)
    return matches >= 2


def has_clarifications_been_asked(messages: list[dict]) -> bool:
    for msg in messages:
        if msg["role"] == "assistant" and "?" in msg["content"]:
            return True
    return False


def build_system_prompt(is_technical: bool, clarifications_asked: bool) -> str:
    if is_technical and not clarifications_asked:
        return SYSTEM_PROMPT + CLARIFICATION_INSTRUCTION
    return SYSTEM_PROMPT
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_question_engine.py -v
```

Expected: all 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/question_engine.py tests/test_question_engine.py
git commit -m "feat: question engine for technical request detection"
```

---

### Task 4: AI Service

**Files:**
- Create: `services/ai_service.py`
- Create: `tests/test_ai_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_ai_service.py`:

```python
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.ai_service import send_message


SAMPLE_MESSAGES = [
    {"role": "user", "content": "Ciao, ho bisogno di aiuto."}
]


@pytest.mark.asyncio
async def test_send_message_claude_returns_string():
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="Risposta di test")]
    mock_client = MagicMock()
    mock_client.messages.create = MagicMock(return_value=mock_message)

    with patch("services.ai_service.anthropic.Anthropic", return_value=mock_client):
        with patch.dict(os.environ, {"CLAUDE_API_KEY": "test-key", "AI_MODEL": "claude"}):
            result = await send_message(SAMPLE_MESSAGES, system_prompt="Test", model="claude")

    assert isinstance(result, str)
    assert result == "Risposta di test"


@pytest.mark.asyncio
async def test_send_message_deepseek_returns_string():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Risposta DeepSeek"}}]
    }

    with patch("services.ai_service.requests.post", return_value=mock_response):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            result = await send_message(SAMPLE_MESSAGES, system_prompt="Test", model="deepseek")

    assert result == "Risposta DeepSeek"


@pytest.mark.asyncio
async def test_send_message_uses_env_default_model():
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="OK")]
    mock_client = MagicMock()
    mock_client.messages.create = MagicMock(return_value=mock_message)

    with patch("services.ai_service.anthropic.Anthropic", return_value=mock_client):
        with patch.dict(os.environ, {"CLAUDE_API_KEY": "key", "AI_MODEL": "claude"}):
            result = await send_message(SAMPLE_MESSAGES, system_prompt="Test")

    assert result == "OK"


@pytest.mark.asyncio
async def test_send_message_raises_on_unknown_model():
    with pytest.raises(ValueError, match="Modello non supportato"):
        await send_message(SAMPLE_MESSAGES, system_prompt="Test", model="gpt-99")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_ai_service.py -v
```

Expected: `ImportError` — `services.ai_service` not found.

- [ ] **Step 3: Implement services/ai_service.py**

```python
import os
import requests
import anthropic


CLAUDE_MODEL = "claude-sonnet-4-20250514"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


async def send_message(
    messages: list[dict],
    system_prompt: str,
    model: str | None = None,
) -> str:
    if model is None:
        model = os.getenv("AI_MODEL", "claude")

    if model == "claude":
        return _send_claude(messages, system_prompt)
    elif model == "deepseek":
        return _send_deepseek(messages, system_prompt)
    else:
        raise ValueError(f"Modello non supportato: {model}")


def _send_claude(messages: list[dict], system_prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=messages,
    )
    return response.content[0].text


def _send_deepseek(messages: list[dict], system_prompt: str) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "max_tokens": 4096,
    }
    response = requests.post(
        DEEPSEEK_API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_ai_service.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/ai_service.py tests/test_ai_service.py
git commit -m "feat: AI service supporting Claude and DeepSeek"
```

---

### Task 5: API Routers

**Files:**
- Create: `api/chat.py`
- Create: `api/history.py`
- Create: `tests/test_chat_api.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_chat_api.py`:

```python
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
            response = await client.post("/api/chat", json={
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
            await client.post("/api/chat", json={
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_chat_api.py -v
```

Expected: `ImportError` or router not found errors.

- [ ] **Step 3: Implement api/chat.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import (
    get_db,
    create_conversation,
    get_conversation,
    delete_conversation,
    create_message,
    get_messages,
)
from services.question_engine import detect_technical_request, has_clarifications_been_asked, build_system_prompt
from services.ai_service import send_message


router = APIRouter()


class ConversationCreate(BaseModel):
    title: str = "Nuova conversazione"


class ChatRequest(BaseModel):
    conversation_id: int
    message: str
    model: str = "claude"


@router.post("/conversations")
async def new_conversation(body: ConversationCreate, db: AsyncSession = Depends(get_db)):
    conv = await create_conversation(db, body.title)
    return {"id": conv.id, "title": conv.title, "created_at": conv.created_at}


@router.delete("/conversations/{conversation_id}")
async def remove_conversation(conversation_id: int, db: AsyncSession = Depends(get_db)):
    conv = await get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversazione non trovata")
    await delete_conversation(db, conversation_id)
    return {"ok": True}


@router.post("/chat")
async def chat(body: ChatRequest, db: AsyncSession = Depends(get_db)):
    conv = await get_conversation(db, body.conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversazione non trovata")

    history = await get_messages(db, body.conversation_id)
    messages_for_ai = [{"role": m.role, "content": m.content} for m in history]

    is_technical = detect_technical_request(body.message)
    clarifications_asked = has_clarifications_been_asked(messages_for_ai)
    system_prompt = build_system_prompt(is_technical, clarifications_asked)

    messages_for_ai.append({"role": "user", "content": body.message})

    reply = await send_message(messages_for_ai, system_prompt=system_prompt, model=body.model)

    await create_message(db, body.conversation_id, "user", body.message)
    await create_message(db, body.conversation_id, "assistant", reply)

    return {"reply": reply, "conversation_id": body.conversation_id}
```

- [ ] **Step 4: Implement api/history.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db, list_conversations, get_conversation, get_messages


router = APIRouter()


@router.get("/conversations")
async def conversations_list(db: AsyncSession = Depends(get_db)):
    convs = await list_conversations(db)
    return [
        {"id": c.id, "title": c.title, "created_at": c.created_at, "updated_at": c.updated_at}
        for c in convs
    ]


@router.get("/conversations/{conversation_id}/messages")
async def conversation_messages(conversation_id: int, db: AsyncSession = Depends(get_db)):
    conv = await get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversazione non trovata")
    msgs = await get_messages(db, conversation_id)
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "image_path": m.image_path,
            "created_at": m.created_at,
        }
        for m in msgs
    ]
```

- [ ] **Step 5: Add pytest.ini for async mode**

Create `pytest.ini` at project root:

```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 6: Run all tests**

```bash
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add api/chat.py api/history.py tests/test_chat_api.py pytest.ini
git commit -m "feat: chat and history API routers"
```

---

### Task 6: Smoke Test and GitHub

**Files:**
- Modify: `main.py` (already complete from Task 1)

- [ ] **Step 1: Start the server with a test .env**

```bash
cp .env.example .env
# Edit .env with a real CLAUDE_API_KEY if available, else leave placeholder
uvicorn main:app --reload
```

Expected: server starts on port 8000, no errors in console.

- [ ] **Step 2: Verify OpenAPI docs load**

Visit `http://localhost:8000/docs` — all endpoints visible: POST /api/conversations, DELETE /api/conversations/{id}, POST /api/chat, GET /api/conversations, GET /api/conversations/{id}/messages.

- [ ] **Step 3: Create GitHub repo and push**

```bash
gh repo create TecnicoAI --public --description "Chatbot tecnico per elettricisti e meccanici italiani" --source=. --remote=origin --push
```

Expected: repo created and code pushed. URL printed in output.

- [ ] **Step 4: Final commit with .gitignore**

Create `.gitignore`:

```
.env
*.db
__pycache__/
*.pyc
.pytest_cache/
.venv/
venv/
```

```bash
git add .gitignore
git commit -m "chore: add gitignore"
git push
```

---

## Self-Review

**Spec coverage:**
- [x] FastAPI + SQLite — Task 1/2
- [x] `conversations` table (id, title, created_at, updated_at) — Task 2
- [x] `messages` table (id, conversation_id, role, content, image_path, created_at) — Task 2
- [x] `send_message(messages, model="claude")` with Claude + DeepSeek — Task 4
- [x] Reads `AI_MODEL` from `.env` as default — Task 4
- [x] `claude-sonnet-4-20250514` for Claude — Task 4
- [x] DeepSeek via requests to `https://api.deepseek.com/v1/chat/completions` — Task 4
- [x] `detect_technical_request(text)` — Task 3
- [x] Clarification injection into system prompt — Task 3
- [x] POST /api/chat — Task 5
- [x] GET /api/conversations — Task 5
- [x] GET /api/conversations/{id} (messages) — Task 5
- [x] DELETE /api/conversations/{id} — Task 5
- [x] POST /api/conversations — Task 5
- [x] System prompt with Italian technical specialization — Task 3
- [x] GitHub push — Task 6
- [x] requirements.txt with all deps — Task 1
- [x] .env.example — Task 1

**Gaps:** None found. `api/history.py` not in original spec's endpoint list but is in file structure — included with GET endpoints, which are a natural fit.
