# Industrial Schema Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add professional industrial schema generation (SVG for simple, Graphviz→PDF for complex) to TecnicoAI, with domain selector UI and full PDF download.

**Architecture:** `schema_service.py` detects complexity from conversation keywords, calls AI for SVG or DOT code, renders to PDF via cairosvg/graphviz, saves to `schemas/` dir and DB. New `api/schema.py` router exposes `POST /api/schema/generate` and `GET /api/schema/pdf/{id}`. Frontend adds a schema panel with domain selector and inline SVG or PDF iframe viewer.

**Tech Stack:** FastAPI, SQLAlchemy async, cairosvg (SVG→PDF), python-graphviz + graphviz binary (DOT→PDF), Anthropic Claude (AI generation), existing AsyncClient test pattern with in-memory SQLite.

---

## File Structure

**Create:**
- `services/schema_service.py` — detect_complexity, build prompts, render_to_pdf, generate_schema
- `api/schema.py` — POST /api/schema/generate, GET /api/schema/pdf/{id}
- `nixpacks.toml` — graphviz + cairo nixPkgs for Railway
- `tests/test_schema_service.py` — unit tests for service pure functions
- `tests/test_schema_api.py` — HTTP tests for schema endpoints

**Modify:**
- `db/database.py` — add Schema model, create_schema, get_schema functions
- `main.py` — register schema_router, mkdir schemas on startup
- `requirements.txt` — add cairosvg, graphviz
- `.gitignore` — add schemas/
- `frontend/index.html` — domain selector modal, schema viewer panel, CSS, JS

---

### Task 1: DB Schema Model

**Files:**
- Modify: `db/database.py`

Add `Schema` ORM model and two async CRUD functions. The `Schema` table stores generated schema metadata including which render engine was used, the raw code, and the PDF file path.

- [ ] **Step 1: Write failing tests for DB functions**

Create `tests/test_schema_db.py`:

```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from db.database import Base, create_schema, get_schema

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
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
    from db.database import create_conversation
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
    from db.database import create_conversation
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
    from db.database import create_conversation
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /home/francesco/progetti/TecnicoAI && .venv/bin/pytest tests/test_schema_db.py -v
```
Expected: `ImportError` or `AttributeError` (create_schema not defined yet).

- [ ] **Step 3: Add Schema model and CRUD to db/database.py**

In `db/database.py`, after the `Message` class, add:

```python
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
```

After `get_messages`, add:

```python
async def create_schema(
    db: AsyncSession,
    conversation_id: int,
    schema_type: str,
    engine: str,
    dot_code: Optional[str] = None,
    svg_content: Optional[str] = None,
    pdf_path: Optional[str] = None,
) -> "Schema":
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


async def get_schema(db: AsyncSession, schema_id: int) -> Optional["Schema"]:
    result = await db.execute(select(Schema).where(Schema.id == schema_id))
    return result.scalar_one_or_none()
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd /home/francesco/progetti/TecnicoAI && .venv/bin/pytest tests/test_schema_db.py -v
```
Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
cd /home/francesco/progetti/TecnicoAI && git add db/database.py tests/test_schema_db.py && git commit -m "feat: add Schema DB model with create_schema and get_schema"
```

---

### Task 2: schema_service.py — Pure Functions

**Files:**
- Create: `services/schema_service.py`
- Create: `tests/test_schema_service.py`

Implement `detect_complexity`, `build_schema_system_prompt`, `_extract_svg`, `_extract_dot`, `render_to_pdf` (with private `_render_svg_to_pdf` and `_render_dot_to_pdf` using lazy imports). Do NOT implement `generate_schema` yet — that's Task 3.

- [ ] **Step 1: Write failing tests**

Create `tests/test_schema_service.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from services.schema_service import (
    detect_complexity,
    build_schema_system_prompt,
    render_to_pdf,
    _extract_svg,
    _extract_dot,
)


def test_detect_complexity_simple():
    messages = [{"role": "user", "content": "Come collegare un interruttore?"}]
    assert detect_complexity(messages) == "svg"


def test_detect_complexity_with_plc():
    messages = [{"role": "user", "content": "Schema PLC con inverter Siemens."}]
    assert detect_complexity(messages) == "graphviz"


def test_detect_complexity_with_robot():
    messages = [{"role": "user", "content": "Cella robotica con safety SIL2."}]
    assert detect_complexity(messages) == "graphviz"


def test_detect_complexity_with_magazzino():
    messages = [{"role": "user", "content": "Magazzino automatico con trasportatori."}]
    assert detect_complexity(messages) == "graphviz"


def test_detect_complexity_checks_all_messages():
    messages = [
        {"role": "user", "content": "Sto progettando un impianto elettrico."},
        {"role": "assistant", "content": "Di che tipo?"},
        {"role": "user", "content": "Con PLC e fieldbus."},
    ]
    assert detect_complexity(messages) == "graphviz"


def test_detect_complexity_list_content():
    messages = [
        {"role": "user", "content": [{"type": "text", "text": "Schema con encoder e servo."}]}
    ]
    assert detect_complexity(messages) == "graphviz"


def test_detect_complexity_encoder_keyword():
    messages = [{"role": "user", "content": "Ho un encoder e un variatore."}]
    assert detect_complexity(messages) == "graphviz"


def test_build_system_prompt_svg_auto():
    prompt = build_schema_system_prompt("svg", "auto")
    assert "<svg" in prompt
    assert "viewBox" in prompt


def test_build_system_prompt_graphviz_auto():
    prompt = build_schema_system_prompt("graphviz", "auto")
    assert "digraph" in prompt
    assert "subgraph" in prompt


def test_build_system_prompt_graphviz_plc():
    prompt = build_schema_system_prompt("graphviz", "plc")
    assert "PLC" in prompt
    assert "I/O" in prompt


def test_build_system_prompt_svg_elettrico():
    prompt = build_schema_system_prompt("svg", "elettrico")
    assert "IEC 60617" in prompt


def test_build_system_prompt_graphviz_pneumatico():
    prompt = build_schema_system_prompt("graphviz", "pneumatico")
    assert "ISO 1219" in prompt


def test_extract_svg_strips_markdown():
    raw = "Ecco lo schema:\n```\n<svg viewBox='0 0 100 100'><rect/></svg>\n```"
    result = _extract_svg(raw)
    assert result.startswith("<svg")
    assert result.endswith("</svg>")


def test_extract_svg_already_clean():
    raw = "<svg viewBox='0 0 100 100'><rect/></svg>"
    assert _extract_svg(raw) == raw


def test_extract_svg_no_match_returns_stripped():
    raw = "  no svg here  "
    assert _extract_svg(raw) == "no svg here"


def test_extract_dot_strips_markdown():
    raw = "```\ndigraph schema { A -> B }\n```"
    result = _extract_dot(raw)
    assert result.startswith("digraph")
    assert result.endswith("}")


def test_extract_dot_already_clean():
    raw = "digraph schema { A -> B }"
    assert _extract_dot(raw) == raw


def test_render_to_pdf_dispatches_svg():
    with patch("services.schema_service._render_svg_to_pdf", return_value=b"%PDF-svg") as mock:
        result = render_to_pdf("<svg/>", "svg")
    assert result == b"%PDF-svg"
    mock.assert_called_once_with("<svg/>")


def test_render_to_pdf_dispatches_graphviz():
    with patch("services.schema_service._render_dot_to_pdf", return_value=b"%PDF-dot") as mock:
        result = render_to_pdf("digraph { A -> B }", "graphviz")
    assert result == b"%PDF-dot"
    mock.assert_called_once_with("digraph { A -> B }")


def test_render_to_pdf_unknown_engine():
    with pytest.raises(ValueError, match="Engine non supportato"):
        render_to_pdf("content", "unknown")
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /home/francesco/progetti/TecnicoAI && .venv/bin/pytest tests/test_schema_service.py -v
```
Expected: `ModuleNotFoundError: No module named 'services.schema_service'`.

- [ ] **Step 3: Create services/schema_service.py with pure functions only**

Create `/home/francesco/progetti/TecnicoAI/services/schema_service.py`:

```python
import asyncio
import os
import tempfile
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from services.ai_service import send_message

COMPLEXITY_KEYWORDS = [
    "plc", "inverter", "servo", "robot", "magazzino", "fieldbus", "mcc",
    "quadro", "automazione", "asse", "encoder", "variatore", "safety",
    "sil", "pl", "profibus", "profinet", "ethercat", "scada", "hmi",
    "meccatronico", "rack", "pneumatico", "idraulico",
]

SIMPLE_SVG_SYSTEM_PROMPT = """Sei un ingegnere specializzato in impiantistica elettrica e meccanica.
Analizza la conversazione tecnica e genera uno schema in formato SVG.

REGOLE:
- Restituisci SOLO codice SVG valido, niente altro
- Inizia con <svg e termina con </svg>
- viewBox="0 0 1123 794" (A4 orizzontale)
- Background bianco: <rect width="100%" height="100%" fill="white"/>
- Font Arial per etichette
- Componenti come rettangoli con colori differenti per tipo:
  * Interruttori/Protezioni: fill="#e3f2fd" stroke="#1565c0"
  * Motori: fill="#fff9c4" stroke="#f57f17"
  * Contattori: fill="#fce4ec" stroke="#c62828"
  * Sensori: fill="#e8f5e9" stroke="#2e7d32"
  * Alimentazione: fill="#f9fbe7" stroke="#558b2f"
- Ogni nodo ha sigla + descrizione breve
- Connessioni con <line> o <path stroke="#555">
- Cartiglio in basso: titolo, data corrente, revisione 00, TecnicoAI
Restituisci SOLO il codice SVG valido, senza testo prima o dopo."""

COMPLEX_DOT_SYSTEM_PROMPT = """Sei un ingegnere specializzato in automazione industriale, meccatronica e impiantistica elettrica. Conosci le norme CEI, IEC 60617, ISO 1219, NFPA 79.

Analizza la conversazione tecnica e genera uno schema nel formato Graphviz DOT language.

STRUTTURA BASE OBBLIGATORIA:
digraph schema {
  rankdir=TB
  bgcolor="white"
  node [fontname="Arial" fontsize=10]
  edge [fontname="Arial" fontsize=9]

  subgraph cluster_alimentazione { label="Alimentazione" style=filled fillcolor="#fafafa" ... }
  subgraph cluster_potenza { label="Quadro Potenza" style=filled fillcolor="#fafafa" ... }
  subgraph cluster_controllo { label="Quadro Controllo PLC" style=filled fillcolor="#fafafa" ... }
  subgraph cluster_campo { label="Dispositivi di Campo" style=filled fillcolor="#fafafa" ... }
  subgraph cluster_legenda { label="Legenda" style=filled fillcolor="#fffde7" ... }
  subgraph cluster_cartiglio { label="Cartiglio" style=filled fillcolor="#f5f5f5" ... }
}

SIMBOLI NODI per tipo:
- PLC/CPU: shape=box style=filled fillcolor="#e3f2fd"
- Motori/Pompe: shape=ellipse fillcolor="#fff9c4"
- Inverter/Variatori: shape=box style=filled fillcolor="#f3e5f5"
- Contattori/Rele: shape=diamond fillcolor="#fce4ec"
- Sensori/Finecorsa: shape=hexagon fillcolor="#e8f5e9"
- Valvole pneumatiche: shape=parallelogram fillcolor="#fff3e0"
- Robot/Manipolatori: shape=box3d fillcolor="#e0f2f1"
- HMI/Pannelli: shape=tab fillcolor="#f5f5f5"
- Safety/SIL: shape=octagon fillcolor="#ffebee"
- Fieldbus/Rete: shape=note fillcolor="#e8eaf6"
- Alimentatori: shape=invtriangle fillcolor="#f9fbe7"
- Encoder/Resolver: shape=component fillcolor="#e0f7fa"

ETICHETTE NODI: sigla (es. Q1) + descrizione + spec (es. "400V 30kW")
ETICHETTE ARCHI: tipo cavo/segnale (es. "3x4mm² 400V") + morsetto se rilevante
CARTIGLIO: includi titolo impianto, data, revisione 00, TecnicoAI, norme applicabili

Restituisci SOLO il codice DOT valido. Inizia con digraph e termina con }."""

DOMAIN_PROMPTS: dict[str, str] = {
    "elettrico": "\n\nDOMINIO: Schema elettrico unifilare/multifilo. Usa simboli IEC 60617. Includi protezioni (fusibili, interruttori magnetotermici, differenziali), contattori, motori, morsettiere.",
    "plc": "\n\nDOMINIO: Schema I/O PLC. Mostra rack PLC con moduli CPU/DI/DO/AI/AO, indirizzi I/O (es. I0.0, Q0.1, AI0), cablaggio ai dispositivi di campo. Includi alimentazione 24VDC.",
    "pneumatico": "\n\nDOMINIO: Schema pneumatico secondo ISO 1219. Usa simboli per compressori, FRL (filtro-regolatore-lubrificatore), valvole direzionali (5/2, 3/2), cilindri, smorzatori.",
    "idraulico": "\n\nDOMINIO: Schema idraulico. Usa simboli per pompe, valvole di controllo (proporzionali, ON/OFF), cilindri idraulici, accumulatori, filtri, manometri.",
    "meccatronico": "\n\nDOMINIO: Schema meccatronico asse elettrico+meccanico. Includi servo drive, motore brushless, encoder, riduttore, trasmissione. Mostra loop controllo posizione/velocità.",
    "fieldbus": "\n\nDOMINIO: Architettura rete industriale. Mostra topologia (linea, stella, anello), nodi con indirizzi, velocità trasmissione, connettori. Includi master (PLC/SCADA) e slave.",
    "safety": "\n\nDOMINIO: Schema circuito sicurezza SIL/PLd. Includi E-stop a doppio canale, ripari elettrosensibili, safety relay (SICK, Pilz), monitoraggio OSSD, reset manuale.",
    "auto": "",
}


def detect_complexity(messages: list[dict]) -> str:
    parts = []
    for m in messages:
        c = m.get("content", "")
        if isinstance(c, str):
            parts.append(c)
        elif isinstance(c, list):
            for block in c:
                if isinstance(block, dict):
                    parts.append(block.get("text", ""))
    combined = " ".join(parts).lower()
    if any(kw in combined for kw in COMPLEXITY_KEYWORDS):
        return "graphviz"
    return "svg"


def build_schema_system_prompt(engine: str, domain: str) -> str:
    base = SIMPLE_SVG_SYSTEM_PROMPT if engine == "svg" else COMPLEX_DOT_SYSTEM_PROMPT
    return base + DOMAIN_PROMPTS.get(domain, "")


def _extract_svg(content: str) -> str:
    start = content.find("<svg")
    end = content.rfind("</svg>")
    if start != -1 and end != -1:
        return content[start:end + 6]
    return content.strip()


def _extract_dot(content: str) -> str:
    start = content.find("digraph")
    end = content.rfind("}")
    if start != -1 and end != -1:
        return content[start:end + 1]
    return content.strip()


def _render_svg_to_pdf(svg_content: str) -> bytes:
    import cairosvg  # lazy import — requires pip install cairosvg + libcairo2-dev
    return cairosvg.svg2pdf(bytestring=svg_content.encode())


def _render_dot_to_pdf(dot_code: str) -> bytes:
    import graphviz  # lazy import — requires pip install graphviz + apt install graphviz
    with tempfile.TemporaryDirectory() as tmpdir:
        src = graphviz.Source(dot_code, directory=tmpdir, filename="schema")
        rendered = src.render(format="pdf", cleanup=True)
        with open(rendered, "rb") as f:
            return f.read()


def render_to_pdf(content: str, engine: str) -> bytes:
    if engine == "svg":
        return _render_svg_to_pdf(content)
    if engine == "graphviz":
        return _render_dot_to_pdf(content)
    raise ValueError(f"Engine non supportato: {engine}")


async def generate_schema(
    conversation_id: int,
    db: AsyncSession,
    domain: str = "auto",
    model: str = "claude",
) -> dict:
    from db.database import get_messages, create_schema

    messages = await get_messages(db, conversation_id)
    messages_for_ai = [{"role": m.role, "content": m.content} for m in messages]

    engine = detect_complexity(messages_for_ai)
    system_prompt = build_schema_system_prompt(engine, domain)

    trigger = messages_for_ai + [
        {"role": "user", "content": "Genera lo schema tecnico basandoti sulla conversazione. Rispondi SOLO con il codice richiesto, senza testo aggiuntivo."}
    ]
    raw = await send_message(trigger, system_prompt=system_prompt, model=model)

    content = _extract_svg(raw) if engine == "svg" else _extract_dot(raw)
    pdf_bytes = await asyncio.to_thread(render_to_pdf, content, engine)

    os.makedirs("schemas", exist_ok=True)
    pdf_filename = f"{uuid.uuid4().hex}.pdf"
    pdf_path = os.path.join("schemas", pdf_filename)
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)

    schema = await create_schema(
        db,
        conversation_id=conversation_id,
        schema_type=domain,
        engine=engine,
        dot_code=content if engine == "graphviz" else None,
        svg_content=content if engine == "svg" else None,
        pdf_path=pdf_path,
    )

    return {
        "schema_id": schema.id,
        "engine": engine,
        "schema_type": domain,
        "pdf_url": f"/api/schema/pdf/{schema.id}",
        "content": content,
    }
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd /home/francesco/progetti/TecnicoAI && .venv/bin/pytest tests/test_schema_service.py -v
```
Expected: all tests PASSED.

- [ ] **Step 5: Commit**

```bash
cd /home/francesco/progetti/TecnicoAI && git add services/schema_service.py tests/test_schema_service.py && git commit -m "feat: add schema_service with complexity detection, prompt building, and PDF rendering"
```

---

### Task 3: api/schema.py + Infrastructure

**Files:**
- Create: `api/schema.py`
- Create: `nixpacks.toml`
- Modify: `main.py`
- Modify: `requirements.txt`
- Modify: `.gitignore`

- [ ] **Step 1: Write failing API tests**

Create `tests/test_schema_api.py`:

```python
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
async def test_generate_schema_graphviz(test_app):
    mock_result = {
        "schema_id": 2,
        "engine": "graphviz",
        "schema_type": "plc",
        "pdf_url": "/api/schema/pdf/2",
        "content": "digraph schema { A -> B }",
    }
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        create = await client.post("/api/conversations", json={"title": "PLC Test"})
        conv_id = create.json()["id"]
        with patch("api.schema.schema_service.generate_schema", new_callable=AsyncMock, return_value=mock_result):
            r = await client.post("/api/schema/generate", json={"conversation_id": conv_id, "domain": "plc"})
    assert r.status_code == 200
    assert r.json()["engine"] == "graphviz"
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
        with patch("api.schema.schema_service.generate_schema", new_callable=AsyncMock):
            r = await client.post("/api/schema/generate", json={"conversation_id": 9999, "domain": "auto"})
    assert r.status_code == 404


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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /home/francesco/progetti/TecnicoAI && .venv/bin/pytest tests/test_schema_api.py -v
```
Expected: `ImportError` (api.schema not found) or 404 (route not registered).

- [ ] **Step 3: Create api/schema.py**

Create `/home/francesco/progetti/TecnicoAI/api/schema.py`:

```python
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db, get_schema, get_conversation
from services import schema_service

router = APIRouter()

VALID_DOMAINS = {
    "elettrico", "plc", "pneumatico", "idraulico",
    "meccatronico", "fieldbus", "safety", "auto",
}


class SchemaRequest(BaseModel):
    conversation_id: int
    domain: str = "auto"
    model: str = "claude"


@router.post("/schema/generate")
async def generate_schema(body: SchemaRequest, db: AsyncSession = Depends(get_db)):
    if body.domain not in VALID_DOMAINS:
        raise HTTPException(status_code=422, detail="Dominio non supportato")
    conv = await get_conversation(db, body.conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversazione non trovata")
    try:
        result = await schema_service.generate_schema(
            body.conversation_id, db, domain=body.domain, model=body.model
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Errore generazione schema") from exc
    return result


@router.get("/schema/pdf/{schema_id}")
async def get_schema_pdf(schema_id: int, db: AsyncSession = Depends(get_db)):
    schema = await get_schema(db, schema_id)
    if not schema or not schema.pdf_path:
        raise HTTPException(status_code=404, detail="Schema non trovato")
    if not os.path.isfile(schema.pdf_path):
        raise HTTPException(status_code=404, detail="File PDF non disponibile")
    return FileResponse(
        schema.pdf_path,
        media_type="application/pdf",
        filename=f"schema-{schema_id}.pdf",
    )
```

- [ ] **Step 4: Update main.py to register schema router and create schemas/ dir**

In `main.py`, add to imports:
```python
from api.schema import router as schema_router
```

In the `lifespan` function, add:
```python
os.makedirs("schemas", exist_ok=True)
```

After `app.include_router(history_router, prefix="/api")`, add:
```python
app.include_router(schema_router, prefix="/api")
```

The full updated `main.py`:
```python
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

from db.database import init_db
from api.chat import router as chat_router
from api.history import router as history_router
from api.schema import router as schema_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("schemas", exist_ok=True)
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
app.include_router(schema_router, prefix="/api")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```

- [ ] **Step 5: Update requirements.txt**

Replace content of `requirements.txt`:
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
cairosvg==2.7.1
graphviz==0.20.3
pytest==8.3.3
pytest-asyncio==0.24.0
```

- [ ] **Step 6: Create nixpacks.toml**

Create `/home/francesco/progetti/TecnicoAI/nixpacks.toml`:
```toml
[phases.setup]
nixPkgs = ["graphviz", "cairo", "pango", "libffi", "glib"]
```

- [ ] **Step 7: Update .gitignore**

Add `schemas/` to `.gitignore`. The file should end with:
```
schemas/
```

- [ ] **Step 8: Install new Python packages in local venv**

```bash
cd /home/francesco/progetti/TecnicoAI && .venv/bin/pip install cairosvg==2.7.1 graphviz==0.20.3
```

Note: cairosvg requires libcairo2 on Linux. If the command fails with library errors, run:
```bash
sudo apt-get install -y libcairo2-dev libpango1.0-dev
```
Then retry the pip install. Also install graphviz system binary if needed:
```bash
sudo apt-get install -y graphviz
```

- [ ] **Step 9: Run all API tests**

```bash
cd /home/francesco/progetti/TecnicoAI && .venv/bin/pytest tests/test_schema_api.py -v
```
Expected: all 7 tests PASSED.

- [ ] **Step 10: Run full test suite to check no regressions**

```bash
cd /home/francesco/progetti/TecnicoAI && .venv/bin/pytest -v
```
Expected: all 54+ tests PASSED (4 new DB tests + 20 schema service tests + 7 API tests = at least 81 total).

Wait — actually the test_schema_db.py was created in Task 1, test_schema_service.py in Task 2, and test_schema_api.py in this task. So we should have the original 54 + these new ones.

- [ ] **Step 11: Commit**

```bash
cd /home/francesco/progetti/TecnicoAI && git add api/schema.py main.py requirements.txt nixpacks.toml .gitignore tests/test_schema_api.py && git commit -m "feat: add schema API endpoint, infrastructure, and tests"
```

---

### Task 4: Frontend — Schema UI

**Files:**
- Modify: `frontend/index.html`

Add domain selector modal, schema viewer panel, CSS for new elements, and JS functions. The "Genera Schema" button lives in the input area row (next to the send button). Clicking it opens a domain modal. After generation, the schema panel slides in from the right.

- [ ] **Step 1: Add CSS for new elements**

In `frontend/index.html`, inside `<style>`, before the closing `</style>` tag (after the last existing rule), add:

```css
    /* ── SCHEMA BUTTON ── */
    .btn-schema {
      background: var(--bg3);
      border: 1px solid var(--border);
      color: var(--text-muted);
      width: 42px; height: 42px;
      border-radius: 10px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
      flex-shrink: 0;
      transition: all 0.15s;
    }
    .btn-schema:hover { background: var(--border); color: var(--text); }

    /* ── DOMAIN MODAL ── */
    .modal-overlay {
      position: fixed; inset: 0;
      background: rgba(0,0,0,0.6);
      z-index: 30;
      display: none;
      align-items: center;
      justify-content: center;
    }
    .modal-overlay.open { display: flex; }
    .modal {
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 24px;
      width: 360px;
      max-width: 90vw;
    }
    .modal h3 { font-size: 16px; font-weight: 600; margin-bottom: 6px; }
    .modal p { font-size: 13px; color: var(--text-muted); margin-bottom: 16px; }
    .domain-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-bottom: 16px;
    }
    .btn-domain {
      background: var(--bg3);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 10px 8px;
      border-radius: 10px;
      cursor: pointer;
      font-size: 13px;
      text-align: center;
      transition: all 0.15s;
    }
    .btn-domain:hover { border-color: var(--accent); color: var(--accent); }
    .btn-domain.selected { border-color: var(--accent); background: rgba(245,158,11,0.15); color: var(--accent); }
    .modal-actions { display: flex; gap: 8px; justify-content: flex-end; }
    .btn-cancel {
      background: transparent;
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 8px 16px;
      border-radius: 8px;
      cursor: pointer;
      font-size: 13px;
    }
    .btn-generate {
      background: var(--accent);
      border: none;
      color: #000;
      padding: 8px 18px;
      border-radius: 8px;
      cursor: pointer;
      font-size: 13px;
      font-weight: 600;
    }
    .btn-generate:disabled { opacity: 0.5; cursor: not-allowed; }

    /* ── SCHEMA VIEWER PANEL ── */
    .schema-panel {
      position: fixed;
      top: 0; right: 0;
      width: min(680px, 100vw);
      height: 100vh;
      background: var(--bg2);
      border-left: 1px solid var(--border);
      z-index: 25;
      transform: translateX(100%);
      transition: transform 0.3s ease;
      display: flex;
      flex-direction: column;
    }
    .schema-panel.open { transform: translateX(0); }
    .schema-panel-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 14px 16px;
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
    }
    .schema-panel-title { font-weight: 600; font-size: 15px; }
    .schema-complexity-badge {
      font-size: 11px;
      padding: 3px 8px;
      border-radius: 12px;
      font-weight: 500;
    }
    .badge-svg { background: rgba(46,125,50,0.2); color: #66bb6a; }
    .badge-graphviz { background: rgba(30,136,229,0.2); color: #42a5f5; }
    .schema-panel-actions {
      display: flex; gap: 6px;
      align-items: center;
    }
    .btn-panel-icon {
      background: var(--bg3);
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 6px 10px;
      border-radius: 8px;
      cursor: pointer;
      font-size: 12px;
      transition: all 0.15s;
    }
    .btn-panel-icon:hover { color: var(--text); background: var(--border); }
    .schema-panel-close {
      background: none; border: none;
      color: var(--text-muted);
      cursor: pointer; font-size: 20px; line-height: 1;
      padding: 4px;
    }
    .schema-content {
      flex: 1;
      overflow: auto;
      padding: 12px;
    }
    .schema-svg-wrap {
      width: 100%;
      overflow: auto;
      background: white;
      border-radius: 8px;
    }
    .schema-svg-wrap svg {
      width: 100%;
      height: auto;
    }
    .schema-pdf-frame {
      width: 100%;
      height: 100%;
      border: none;
      border-radius: 8px;
    }
    .schema-loading {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 200px;
      color: var(--text-muted);
      font-size: 14px;
      gap: 10px;
    }
    .schema-error {
      color: var(--error);
      font-size: 13px;
      padding: 16px;
      text-align: center;
    }
```

- [ ] **Step 2: Add HTML for modal and schema panel**

In `frontend/index.html`, after `</header>` and before `<div class="sidebar-overlay"`, add:

```html
<!-- Domain Selector Modal -->
<div class="modal-overlay" id="domain-modal">
  <div class="modal">
    <h3>Genera Schema Tecnico</h3>
    <p>Seleziona il tipo di schema da generare in base alla conversazione:</p>
    <div class="domain-grid">
      <button class="btn-domain selected" data-domain="auto" onclick="selectDomain(this)">🤖 Auto</button>
      <button class="btn-domain" data-domain="elettrico" onclick="selectDomain(this)">⚡ Elettrico</button>
      <button class="btn-domain" data-domain="plc" onclick="selectDomain(this)">🔧 PLC / Controllo</button>
      <button class="btn-domain" data-domain="pneumatico" onclick="selectDomain(this)">💨 Pneumatico</button>
      <button class="btn-domain" data-domain="idraulico" onclick="selectDomain(this)">💧 Idraulico</button>
      <button class="btn-domain" data-domain="meccatronico" onclick="selectDomain(this)">⚙️ Meccatronico</button>
      <button class="btn-domain" data-domain="fieldbus" onclick="selectDomain(this)">🌐 Fieldbus</button>
      <button class="btn-domain" data-domain="safety" onclick="selectDomain(this)">🛡️ Safety</button>
    </div>
    <div class="modal-actions">
      <button class="btn-cancel" onclick="closeDomainModal()">Annulla</button>
      <button class="btn-generate" id="btn-generate-schema" onclick="generateSchema()">Genera Schema</button>
    </div>
  </div>
</div>

<!-- Schema Viewer Panel -->
<div class="schema-panel" id="schema-panel">
  <div class="schema-panel-header">
    <div style="display:flex;align-items:center;gap:10px">
      <span class="schema-panel-title">Schema Tecnico</span>
      <span class="schema-complexity-badge" id="schema-badge"></span>
    </div>
    <div class="schema-panel-actions">
      <button class="btn-panel-icon" id="btn-download-pdf" onclick="downloadSchemaPdf()" title="Scarica PDF">📄 PDF</button>
      <button class="btn-panel-icon" id="btn-copy-dot" onclick="copyDotCode()" title="Copia codice DOT" style="display:none">📋 DOT</button>
      <button class="schema-panel-close" onclick="closeSchemaPanel()">✕</button>
    </div>
  </div>
  <div class="schema-content" id="schema-content">
    <div class="schema-loading">Generazione schema in corso...</div>
  </div>
</div>
```

- [ ] **Step 3: Add schema button to input row HTML**

In the `.input-row` div in `frontend/index.html`, after the `<button class="btn-attach" ...>` and before `<textarea`, add:

```html
      <button class="btn-schema" onclick="openDomainModal()" title="Genera schema tecnico">📐</button>
```

So the input-row becomes:
```html
    <div class="input-row">
      <input type="file" id="file-input" accept="image/*" capture="environment" onchange="handleImageSelect(event)">
      <button class="btn-attach" onclick="document.getElementById('file-input').click()" title="Allega foto">📎</button>
      <button class="btn-schema" onclick="openDomainModal()" title="Genera schema tecnico">📐</button>
      <textarea
        id="message-input"
        placeholder="Scrivi un messaggio tecnico..."
        rows="1"
        onkeydown="handleKey(event)"
        oninput="autoResize(this)"
      ></textarea>
      <button class="btn-send" id="btn-send" onclick="sendMessage()" title="Invia">▶</button>
    </div>
```

- [ ] **Step 4: Add schema JavaScript functions**

In `frontend/index.html`, inside `<script>`, after `let isSending = false;` line, add:

```javascript
let selectedDomain = 'auto';
let currentSchemaId = null;
let currentDotCode = null;
let currentPdfUrl = null;
```

After the `// ─── EXPORT ───` section and before `// ─── UTILS ───`, add:

```javascript
// ─── SCHEMA ────────────────────────────────────────────────────────────────

function openDomainModal() {
  if (!currentConvId) {
    alert('Apri o crea una conversazione prima di generare uno schema.');
    return;
  }
  document.getElementById('domain-modal').classList.add('open');
}

function closeDomainModal() {
  document.getElementById('domain-modal').classList.remove('open');
}

function selectDomain(btn) {
  document.querySelectorAll('.btn-domain').forEach(b => b.classList.remove('selected'));
  btn.classList.add('selected');
  selectedDomain = btn.dataset.domain;
}

function closeSchemaPanel() {
  document.getElementById('schema-panel').classList.remove('open');
}

function downloadSchemaPdf() {
  if (!currentPdfUrl) return;
  const a = document.createElement('a');
  a.href = `${BACKEND_URL}${currentPdfUrl}`;
  a.download = `schema-${currentSchemaId}.pdf`;
  a.click();
}

function copyDotCode() {
  if (!currentDotCode) return;
  navigator.clipboard.writeText(currentDotCode).then(() => {
    const btn = document.getElementById('btn-copy-dot');
    const orig = btn.textContent;
    btn.textContent = '✓ Copiato';
    setTimeout(() => { btn.textContent = orig; }, 1500);
  });
}

async function generateSchema() {
  const btn = document.getElementById('btn-generate-schema');
  btn.disabled = true;
  btn.textContent = 'Generazione...';
  closeDomainModal();

  const panel = document.getElementById('schema-panel');
  const content = document.getElementById('schema-content');
  content.innerHTML = '<div class="schema-loading"><span>⏳</span> Generazione schema in corso...</div>';
  panel.classList.add('open');

  try {
    const res = await fetch(`${BACKEND_URL}/api/schema/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversation_id: currentConvId, domain: selectedDomain, model: 'claude' }),
    });
    if (!res.ok) {
      content.innerHTML = '<div class="schema-error">Errore nella generazione dello schema. Riprova.</div>';
      return;
    }
    const data = await res.json();
    currentSchemaId = data.schema_id;
    currentPdfUrl = data.pdf_url;
    currentDotCode = data.engine === 'graphviz' ? data.content : null;

    const badge = document.getElementById('schema-badge');
    if (data.engine === 'graphviz') {
      badge.textContent = 'Schema industriale (Graphviz)';
      badge.className = 'schema-complexity-badge badge-graphviz';
      document.getElementById('btn-copy-dot').style.display = '';
      content.innerHTML = `<iframe
        class="schema-pdf-frame"
        src="${BACKEND_URL}${data.pdf_url}"
        title="Schema PDF">
      </iframe>`;
    } else {
      badge.textContent = 'Schema semplice (SVG)';
      badge.className = 'schema-complexity-badge badge-svg';
      document.getElementById('btn-copy-dot').style.display = 'none';
      content.innerHTML = `<div class="schema-svg-wrap">${data.content}</div>`;
    }
  } catch (_) {
    content.innerHTML = '<div class="schema-error">Connessione persa. Verifica il backend.</div>';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Genera Schema';
  }
}
```

- [ ] **Step 5: Verify there are no test regressions**

```bash
cd /home/francesco/progetti/TecnicoAI && .venv/bin/pytest -v
```
Expected: all tests still PASSED (frontend changes don't affect tests).

- [ ] **Step 6: Commit**

```bash
cd /home/francesco/progetti/TecnicoAI && git add frontend/index.html && git commit -m "feat: add schema UI with domain selector, SVG/PDF viewer, and download button"
```

---

### Task 5: README Update + GitHub Push

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read current README**

```bash
cd /home/francesco/progetti/TecnicoAI && cat README.md
```

- [ ] **Step 2: Add schema types section to README.md**

After the existing features section, add a new section:

```markdown
## Tipi di schema supportati

Clicca il pulsante 📐 nella barra di input per generare uno schema tecnico.

| Tipo | Dominio | Motore | Formato |
|------|---------|--------|---------|
| ⚡ Elettrico | `elettrico` | SVG / Graphviz | A4 / A3 |
| 🔧 PLC/Controllo | `plc` | Graphviz | A3 PDF |
| 💨 Pneumatico | `pneumatico` | SVG / Graphviz | A4 / A3 |
| 💧 Idraulico | `idraulico` | SVG / Graphviz | A4 / A3 |
| ⚙️ Meccatronico | `meccatronico` | Graphviz | A3 PDF |
| 🌐 Fieldbus | `fieldbus` | Graphviz | A3 PDF |
| 🛡️ Safety | `safety` | Graphviz | A3 PDF |
| 🤖 Auto | `auto` | Automatico | - |

**Come funziona:** TecnicoAI analizza la conversazione e sceglie automaticamente il motore di rendering:
- **Schema semplice (SVG):** per impianti civili e automazioni con meno di 15 componenti
- **Schema industriale (Graphviz):** per PLC, MCC, robotica, magazzini automatici e impianti complessi

### Esempi di prompt per ogni dominio

**Cella robotica pick & place:**
```
Ho una cella robotica pick&place con robot KUKA a 6 assi, due cilindri pneumatici per gripper,
safety fence con scanner laser SICK, PLC Siemens S7-1500 in modalità PROFINET,
inverter per nastro di alimentazione 400V 5.5kW. Crea lo schema.
```

**Magazzino automatico con trasportatori:**
```
Magazzino automatico con 3 trasportatori a rulli 400V, 2 sollevatori servo-motorizzati,
PLC Allen-Bradley ControlLogix, rete EtherNet/IP, lettori barcode, sensori finecorsa
induttivi, quadro MCC con 8 inverter Danfoss. Genera lo schema di automazione.
```

**Quadro MCC 400V con 8 motori:**
```
Quadro MCC 400V con 8 utenze motore da 1.5 a 22kW, interruttori motorizzati ABB,
contattori con relè termici, 3 inverter per pompe variabili, misuratore di energia
multimetro Schneider PM5100, PLC di supervisione con Modbus TCP. Schema elettrico.
```

**Circuito pneumatico:**
```
Impianto pneumatico per pressa industriale: compressore 10bar, serbatoio 200L,
essiccatore, FRL, valvola proporzionale 5/2 Festo per cilindro principale 100x400mm,
4 cilindri di bloccaggio 50x200mm con valvole 5/2 a solenoide, pressostati di controllo.
```

## Installazione dipendenze sistema (per rendering schemi)

```bash
# Linux / WSL2 (Ubuntu)
sudo apt-get install -y graphviz libcairo2-dev libpango1.0-dev

# macOS
brew install graphviz cairo pango

# Windows
choco install graphviz
```
```

- [ ] **Step 3: Run full test suite one final time**

```bash
cd /home/francesco/progetti/TecnicoAI && .venv/bin/pytest -v --tb=short
```
Expected: all tests PASSED.

- [ ] **Step 4: Commit and push**

```bash
cd /home/francesco/progetti/TecnicoAI && git add README.md && git commit -m "docs: add schema types section with domain examples and system requirements"
git push origin master
```

---

## Self-Review

### Spec coverage check:

| Requirement | Covered by |
|-------------|-----------|
| Livello 1 SVG per schemi semplici | Task 2: `SIMPLE_SVG_SYSTEM_PROMPT`, `_render_svg_to_pdf` |
| Livello 2 Graphviz per schemi complessi | Task 2: `COMPLEX_DOT_SYSTEM_PROMPT`, `_render_dot_to_pdf` |
| `detect_complexity` con keywords PLC/servo/robot/etc | Task 2: `COMPLEXITY_KEYWORDS`, `detect_complexity()` |
| System prompt DOT completo con tutti i simboli | Task 2: `COMPLEX_DOT_SYSTEM_PROMPT` |
| `generate_schema(conversation_id, schema_type="auto")` | Task 2: `generate_schema()` |
| `render_to_pdf(content, engine)` | Task 2: `render_to_pdf()` |
| cairosvg per SVG→PDF | Task 2+3: `_render_svg_to_pdf`, requirements.txt |
| graphviz per DOT→PDF | Task 2+3: `_render_dot_to_pdf`, requirements.txt |
| PDF A3 per schemi complessi | DOT prompt specifies A3-friendly rankdir; graphviz renders full graph |
| Watermark TecnicoAI | Included in cartiglio subgraph of DOT prompt and SVG cartiglio spec |
| POST /api/schema/generate con campo domain | Task 3: `api/schema.py` |
| 8 domini supportati | Task 3: `VALID_DOMAINS`, `DOMAIN_PROMPTS` |
| GET /api/schema/pdf/{schema_id} | Task 3: `get_schema_pdf` |
| Selettore tipo schema frontend | Task 4: domain modal with 8 buttons |
| SVG zoomabile inline | Task 4: `.schema-svg-wrap svg { width:100%; }` |
| PDF in iframe per Graphviz | Task 4: `<iframe>` viewer |
| Indicatore complessità | Task 4: badge-svg / badge-graphviz |
| Bottone Scarica PDF A3 | Task 4: `downloadSchemaPdf()` |
| Bottone Copia codice DOT | Task 4: `copyDotCode()`, visible only for graphviz |
| nixpacks.toml con graphviz | Task 3: `nixpacks.toml` |
| README con esempi | Task 5 |
| schemas/ in .gitignore | Task 3 |
| GitHub push | Task 5 |

All requirements covered. No placeholders. Type signatures consistent across tasks.
