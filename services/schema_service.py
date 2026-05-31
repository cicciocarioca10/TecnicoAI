import asyncio
import os
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from services.ai_service import send_message

SVG_SYSTEM_PROMPT = """Sei un ingegnere specializzato in impiantistica elettrica, meccanica e automazione industriale. Conosci le norme CEI, IEC 60617, ISO 1219, NFPA 79.
Analizza la conversazione tecnica e genera uno schema completo in formato SVG.

REGOLE OBBLIGATORIE:
- Restituisci SOLO codice SVG valido, niente altro
- Inizia con <svg e termina con </svg>
- viewBox="0 0 1123 794" (A4 orizzontale)
- Background bianco: <rect width="100%" height="100%" fill="white"/>
- Font Arial o sans-serif per tutte le etichette
- Usa <defs> per definire marker freccia: <marker id="arrow" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#555"/></marker>

COLORI PER TIPO COMPONENTE:
- Alimentazione/Rete: fill="#f9fbe7" stroke="#558b2f" (verde chiaro)
- Interruttori/Protezioni/Fusibili: fill="#e3f2fd" stroke="#1565c0" (blu chiaro)
- Contattori/Rele: fill="#fce4ec" stroke="#c62828" (rosa)
- Motori/Pompe: fill="#fff9c4" stroke="#f57f17" (giallo)
- PLC/CPU/Moduli I/O: fill="#e8eaf6" stroke="#3949ab" (viola chiaro)
- Inverter/Variatori: fill="#f3e5f5" stroke="#7b1fa2" (lilla)
- Sensori/Trasduttori/Finecorsa: fill="#e8f5e9" stroke="#2e7d32" (verde)
- Valvole/Attuatori: fill="#fff3e0" stroke="#e65100" (arancio)
- Safety/Emergenza/E-stop: fill="#ffebee" stroke="#b71c1c" (rosso chiaro)
- Fieldbus/Comunicazione/HMI: fill="#e0f2f1" stroke="#00695c" (teal)

STRUTTURA SCHEMA (usa <g id="..."> per raggruppare sezioni con etichetta di sezione):
1. Sezione ALIMENTAZIONE (in alto, y 20-120): sorgente rete, generale, protezioni principali
2. Sezione POTENZA (area centrale sx, y 130-420): quadro potenza, contattori, motori, inverter
3. Sezione CONTROLLO (area centrale dx, y 130-420): PLC rack, relè comando, alimentatore 24VDC
4. Sezione CAMPO (y 430-580): sensori, attuatori, valvole, dispositivi di campo
5. LEGENDA (angolo basso sx, y 600-760): rettangoli colorati con descrizione tipo componente
6. CARTIGLIO (banda bassa dx, y 600-760): titolo impianto, data odierna, Rev.00, TecnicoAI, norma

SIMBOLI SVG:
- Ogni componente: <rect rx="4" ry="4"> con colori del tipo + <text> sigla + descrizione
- Sigla: <text font-size="11" font-weight="bold"> centrata nel rettangolo
- Descrizione: <text font-size="9"> sotto la sigla
- Specifiche tecniche: <text font-size="8" fill="#666"> ancora sotto
- PLC rack: rettangolo largo (min 300px) diviso da linee verticali in celle etichettate (CPU|DI|DO|AI|AO)
- Bus fieldbus: linea orizzontale spessa stroke-width="4" con derivazioni verticali ai nodi
- Safety relay: rettangolo con doppio bordo (aggiungere secondo rect leggermente piu grande)
- Connessioni: <line> o <polyline stroke="#555" stroke-width="1.5" marker-end="url(#arrow)">
- Connessioni bus di potenza: stroke-width="3" stroke="#333"

ETICHETTE:
- font-family="Arial,sans-serif" su tutti i <text>
- Sigla bold: font-size="11" font-weight="bold" text-anchor="middle"
- Descrizione: font-size="9" text-anchor="middle"
- Specifiche: font-size="8" fill="#666" text-anchor="middle"
- Etichette sezione: font-size="12" font-weight="bold" fill="#333"
- Etichette connessione (cavo, segnale): font-size="8" fill="#777"

QUALITA SCHEMA:
- Disponi i componenti senza sovrapposizioni, con spaziatura adeguata
- Le connessioni devono seguire percorsi ortogonali (angoli retti)
- Inserisci TUTTI i componenti menzionati nella conversazione
- Scala le dimensioni in base al numero di componenti

Restituisci SOLO il codice SVG valido, senza testo prima o dopo."""

DOMAIN_PROMPTS: dict[str, str] = {
    "elettrico": "\n\nDOMINIO ELETTRICO: Schema unifilare/multifilo secondo IEC 60617. Includi protezioni (fusibili, interruttori magnetotermici, differenziali), contattori, motori, morsettiere. Mostra le sezioni cavo.",
    "plc": "\n\nDOMINIO PLC: Schema I/O. Disegna il rack PLC con celle CPU/DI/DO/AI/AO etichettate con indirizzi I/O (es. I0.0, Q0.1, AI0). Cablaggio ai dispositivi di campo. Alimentazione 24VDC separata.",
    "pneumatico": "\n\nDOMINIO PNEUMATICO: Schema secondo ISO 1219. Compressore, FRL (filtro-regolatore-lubrificatore), valvole direzionali (5/2, 3/2), cilindri a semplice/doppio effetto, smorzatori.",
    "idraulico": "\n\nDOMINIO IDRAULICO: Pompa idraulica, valvole di controllo (proporzionali e ON/OFF), cilindri idraulici, accumulatori, filtri, manometri, serbatoio olio.",
    "meccatronico": "\n\nDOMINIO MECCATRONICO: Servo drive, motore brushless, encoder, riduttore meccanico, trasmissione. Mostra il loop di controllo posizione/velocita/coppia con frecce bidirezionali.",
    "fieldbus": "\n\nDOMINIO FIELDBUS: Topologia di rete industriale (linea/stella/anello). Bus orizzontale spesso con nodi master (PLC/SCADA) e slave etichettati con indirizzo e tipo. Velocita trasmissione e connettori.",
    "safety": "\n\nDOMINIO SAFETY SIL/PLd: E-stop a doppio canale (due linee parallele), ripari elettrosensibili, safety relay (SICK/Pilz) con uscite OSSD, reset manuale. Evidenzia il doppio canale con colori diversi.",
    "auto": "",
}


def build_schema_system_prompt(domain: str) -> str:
    return SVG_SYSTEM_PROMPT + DOMAIN_PROMPTS.get(domain, "")


def _extract_svg(content: str) -> str:
    start = content.find("<svg")
    if start == -1:
        return content.strip()
    end = content.find("</svg>", start)
    if end == -1:
        return content.strip()
    return content[start:end + 6]


def _render_svg_to_pdf(svg_content: str) -> bytes:
    import cairosvg  # lazy import — requires pip install cairosvg + libcairo2-dev
    return cairosvg.svg2pdf(bytestring=svg_content.encode())


def render_to_pdf(content: str, engine: str) -> bytes:
    if engine == "svg":
        return _render_svg_to_pdf(content)
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

    engine = "svg"
    system_prompt = build_schema_system_prompt(domain)

    trigger = messages_for_ai + [
        {"role": "user", "content": "Genera lo schema tecnico basandoti sulla conversazione. Rispondi SOLO con il codice SVG richiesto, senza testo aggiuntivo."}
    ]
    raw = await send_message(trigger, system_prompt=system_prompt, model=model)

    content = _extract_svg(raw)

    pdf_bytes = await asyncio.to_thread(render_to_pdf, content, engine)

    os.makedirs("schemas", exist_ok=True)
    pdf_filename = f"{uuid.uuid4().hex}.pdf"
    pdf_path = os.path.join("schemas", pdf_filename)
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)

    try:
        schema = await create_schema(
            db,
            conversation_id=conversation_id,
            schema_type=domain,
            engine=engine,
            dot_code=None,
            svg_content=content,
            pdf_path=pdf_path,
        )
    except Exception:
        try:
            os.unlink(pdf_path)
        except OSError:
            pass
        raise

    return {
        "schema_id": schema.id,
        "engine": engine,
        "schema_type": domain,
        "pdf_url": f"/api/schema/pdf/{schema.id}",
        "content": content,
    }
