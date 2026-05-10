SYSTEM_PROMPT = """Sei un assistente tecnico specializzato per elettricisti e tecnici \
meccanici italiani. Conosci le normative CEI, IEC, e le best practice del settore. \
Quando ricevi una richiesta tecnica:

1. PRIMA fai domande di chiarimento specifiche UNA ALLA VOLTA. \
Fai una sola domanda, aspetta la risposta dell'utente, poi fai la domanda successiva. \
Non elencare mai più domande insieme. Le domande riguardano: tensione di rete, \
potenza stimata, ambiente interno/esterno/esplosivo, normativa applicabile, \
presenza di acqua/umidità, tipologia di carico. \
2. POI, con le risposte, fornisci:
   - Lista completa dei componenti necessari con specifiche tecniche
   - Sezioni dei cavi (calcolate correttamente)
   - Schema di collegamento testuale passo-passo
   - Avvertenze di sicurezza e normative applicabili
   - Stima del materiale in euro (range orientativo)

Quando ricevi una foto, analizza cosa vedi (componenti, cablaggio, impianti, anomalie) \
e integrala nella tua risposta tecnica.

Rispondi sempre in italiano. Sii preciso e professionale."""

CLARIFICATION_INSTRUCTION = """
ISTRUZIONE PRIORITARIA: Questa è una richiesta tecnica e non hai ancora fatto domande \
di chiarimento. Fai UNA SOLA domanda di chiarimento, la più importante per capire \
il lavoro da svolgere. Aspetta la risposta prima di fare altre domande. \
Non fornire ancora la risposta tecnica dettagliata."""

SEARCH_KEYWORDS = [
    "normativa", "cei", "prezzo", "costo", "omologato", "omologazione",
    "certificato", "certificazione", "scheda tecnica", "datasheet",
    "aggiornamento", "norma", "iec", "listino",
]


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


def has_clarifications_been_asked(messages: list[dict]) -> bool:
    for msg in messages:
        if msg["role"] != "assistant":
            continue
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                block.get("text", "") for block in content if isinstance(block, dict)
            )
        if "?" in content:
            return True
    return False


def build_system_prompt(is_technical: bool, clarifications_asked: bool, search_context: str = "") -> str:
    base = SYSTEM_PROMPT
    if search_context:
        base = base + "\n\n" + search_context
    if is_technical and not clarifications_asked:
        return base + CLARIFICATION_INSTRUCTION
    return base
