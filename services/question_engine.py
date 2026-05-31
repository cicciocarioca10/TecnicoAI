SYSTEM_PROMPT = """Sei un assistente tecnico specializzato per elettricisti e tecnici \
meccanici italiani. Conosci le normative CEI, IEC, e le best practice del settore. \
Quando ricevi una richiesta tecnica:

1. PRIMA fai domande di chiarimento specifiche UNA ALLA VOLTA. \
Fai una sola domanda, aspetta la risposta dell'utente, poi fai la domanda successiva. \
Non elencare mai piu domande insieme.
2. POI, con le risposte, fornisci:
   - Lista completa dei componenti necessari con specifiche tecniche
   - Sezioni dei cavi (calcolate correttamente)
   - Schema di collegamento testuale passo-passo
   - Avvertenze di sicurezza e normative applicabili
   - Stima del materiale in euro (range orientativo)

Quando ricevi una foto, analizza cosa vedi (componenti, cablaggio, impianti, anomalie) \
e integrala nella tua risposta tecnica.

Rispondi sempre in italiano. Sii preciso e professionale."""

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "elettrico": [
        "tensione", "corrente", "kw", "kva", "volt", "interruttore",
        "differenziale", "magnetotermico", "cavo", "sezione", "quadro",
        "messa a terra", "cei", "monofase", "trifase", "impianto elettrico",
        "contattore", "fusibile", "relè", "trasformatore",
    ],
    "idraulico": [
        "pompa", "valvola", "cilindro", "idraulico", "olio", "portata",
        "pressione", "bar", "accumulatore", "circuito idraulico", "manometro",
    ],
    "pneumatico": [
        "pneumatico", "aria compressa", "compressore", "frl",
        "valvola 5/2", "valvola 3/2", "attuatore pneumatico", "cilindro pneumatico",
    ],
    "plc": [
        "plc", "automazione", "scada", "hmi", "profibus", "profinet",
        "ethercat", "fieldbus", "cpu", "modulo io", "inverter", "servo",
    ],
}

DOMAIN_CLARIFICATION_INSTRUCTIONS: dict[str, str] = {
    "elettrico": """
ISTRUZIONE PRIORITARIA: Richiesta tecnica elettrica rilevata. Devi raccogliere le seguenti \
informazioni PRIMA di fornire la risposta tecnica. Fai UNA SOLA domanda alla volta, \
aspetta la risposta, poi passa alla successiva.
Informazioni critiche da raccogliere (in ordine di priorita):
1. Tensione di rete (230V monofase / 400V trifase)
2. Potenza totale stimata in kW e numero di carichi
3. Ambiente di installazione (interno/esterno, IP richiesto, zona ATEX?)
4. Normativa applicabile (impianto civile CEI 64-8 / industriale / altro)
5. Presenza di differenziale esistente e tipo di messa a terra (TT/TN/IT)
Fai la domanda piu critica tra quelle ancora senza risposta. Non fornire ancora la risposta tecnica dettagliata.""",

    "idraulico": """
ISTRUZIONE PRIORITARIA: Richiesta tecnica idraulica rilevata. Devi raccogliere le seguenti \
informazioni PRIMA di fornire la risposta tecnica. Fai UNA SOLA domanda alla volta.
Informazioni critiche da raccogliere:
1. Portata richiesta (litri/min)
2. Pressione di esercizio (bar) e pressione massima ammissibile
3. Tipo di fluido (olio minerale / biodegradabile / altro)
4. Tipo di attuatori (cilindri / motori idraulici) e loro numero
5. Ciclo operativo (continuo / intermittente) e temperatura ambiente
Fai la domanda piu critica ancora senza risposta.""",

    "pneumatico": """
ISTRUZIONE PRIORITARIA: Richiesta tecnica pneumatica rilevata. Devi raccogliere le seguenti \
informazioni PRIMA di fornire la risposta tecnica. Fai UNA SOLA domanda alla volta.
Informazioni critiche da raccogliere:
1. Pressione di alimentazione disponibile (bar) e qualita dell'aria (ISO 8573)
2. Consumo aria stimato (litri/min o Nl/min)
3. Tipo di attuatori (cilindri a semplice/doppio effetto, rotanti, pinze)
4. Velocita e frequenza del ciclo operativo
5. Presenza di zona ATEX o requisiti safety (ISO 13849)
Fai la domanda piu critica ancora senza risposta.""",

    "plc": """
ISTRUZIONE PRIORITARIA: Richiesta tecnica PLC/automazione rilevata. Devi raccogliere le seguenti \
informazioni PRIMA di fornire la risposta tecnica. Fai UNA SOLA domanda alla volta.
Informazioni critiche da raccogliere:
1. Marca e modello PLC preferito (Siemens/Allen-Bradley/Omron/altro) o aperto
2. Numero di I/O digitali (DI/DO) e analogici (AI/AO) necessari
3. Protocollo fieldbus richiesto (Profibus/Profinet/EtherCAT/Modbus/nessuno)
4. Livello di sicurezza funzionale richiesto (PLd/SIL2/nessuno)
5. Presenza di HMI o SCADA e tipo di supervisione remota
Fai la domanda piu critica ancora senza risposta.""",

    "generale": """
ISTRUZIONE PRIORITARIA: Questa e una richiesta tecnica e non hai ancora raccolto \
informazioni sufficienti. Fai UNA SOLA domanda di chiarimento, la piu importante \
per capire il lavoro da svolgere. Aspetta la risposta prima di fare altre domande. \
Non fornire ancora la risposta tecnica dettagliata.""",
}

SEARCH_KEYWORDS = [
    "normativa", "cei", "prezzo", "costo", "omologato", "omologazione",
    "certificato", "certificazione", "scheda tecnica", "datasheet",
    "aggiornamento", "norma", "iec", "listino",
]

MIN_CLARIFICATION_EXCHANGES = 3


def should_search(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in SEARCH_KEYWORDS)


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


def _extract_content(msg: dict) -> str:
    content = msg.get("content", "")
    if isinstance(content, list):
        return " ".join(
            block.get("text", "") for block in content if isinstance(block, dict)
        )
    return content


def count_clarification_exchanges(messages: list[dict]) -> int:
    """Count complete Q&A pairs: AI asked a question AND user replied."""
    count = 0
    last_assistant_asked = False
    for msg in messages:
        content = _extract_content(msg)
        if msg["role"] == "assistant" and "?" in content:
            last_assistant_asked = True
        elif msg["role"] == "user" and last_assistant_asked:
            count += 1
            last_assistant_asked = False
    return count


def has_clarifications_been_asked(messages: list[dict]) -> bool:
    return count_clarification_exchanges(messages) >= MIN_CLARIFICATION_EXCHANGES


def detect_domain(messages: list[dict]) -> str:
    text = " ".join(_extract_content(m) for m in messages).lower()
    scores = {
        domain: sum(1 for kw in kws if kw in text)
        for domain, kws in DOMAIN_KEYWORDS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] >= 1 else "generale"


def build_system_prompt(
    is_technical: bool,
    clarifications_asked: bool,
    search_context: str = "",
    messages: list[dict] | None = None,
) -> str:
    base = SYSTEM_PROMPT
    if search_context:
        base = base + "\n\n" + search_context
    if is_technical and not clarifications_asked:
        domain = detect_domain(messages or [])
        instruction = DOMAIN_CLARIFICATION_INSTRUCTIONS.get(
            domain, DOMAIN_CLARIFICATION_INSTRUCTIONS["generale"]
        )
        return base + instruction
    return base
