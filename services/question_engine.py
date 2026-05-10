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


def build_system_prompt(is_technical: bool, clarifications_asked: bool) -> str:
    if is_technical and not clarifications_asked:
        return SYSTEM_PROMPT + CLARIFICATION_INSTRUCTION
    return SYSTEM_PROMPT
