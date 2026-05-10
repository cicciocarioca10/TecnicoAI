import asyncio
import os
import tempfile
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from services.ai_service import send_message

COMPLEXITY_KEYWORDS = [
    "plc", "inverter", "servo", "robot", "magazzino", "fieldbus", "mcc",
    "quadro", "automazione", "asse", "encoder", "variatore", "safety",
    "sil", "pld", "profibus", "profinet", "ethercat", "scada", "hmi",
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
        if m.get("role") != "user":
            continue
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
    if start == -1:
        return content.strip()
    end = content.find("</svg>", start)
    if end == -1:
        return content.strip()
    return content[start:end + 6]


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
