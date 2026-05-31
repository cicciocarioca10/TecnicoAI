from services.question_engine import (
    detect_technical_request,
    has_clarifications_been_asked,
    count_clarification_exchanges,
    detect_domain,
    build_system_prompt,
    should_search,
)


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


# ─── count_clarification_exchanges ─────────────────────────────────────────

def test_count_exchanges_empty():
    assert count_clarification_exchanges([]) == 0


def test_count_exchanges_only_user():
    messages = [{"role": "user", "content": "Voglio installare un impianto."}]
    assert count_clarification_exchanges(messages) == 0


def test_count_exchanges_assistant_no_question():
    messages = [
        {"role": "user", "content": "Ciao."},
        {"role": "assistant", "content": "Benvenuto, come posso aiutarti."},
    ]
    assert count_clarification_exchanges(messages) == 0


def test_count_exchanges_one_complete():
    messages = [
        {"role": "user", "content": "Voglio installare un impianto."},
        {"role": "assistant", "content": "Qual e la tensione di rete?"},
        {"role": "user", "content": "400V trifase."},
    ]
    assert count_clarification_exchanges(messages) == 1


def test_count_exchanges_two_complete():
    messages = [
        {"role": "user", "content": "Impianto industriale."},
        {"role": "assistant", "content": "Qual e la tensione?"},
        {"role": "user", "content": "400V."},
        {"role": "assistant", "content": "Qual e la potenza?"},
        {"role": "user", "content": "30kW."},
    ]
    assert count_clarification_exchanges(messages) == 2


def test_count_exchanges_three_complete():
    messages = [
        {"role": "user", "content": "Impianto industriale."},
        {"role": "assistant", "content": "Qual e la tensione?"},
        {"role": "user", "content": "400V."},
        {"role": "assistant", "content": "Qual e la potenza?"},
        {"role": "user", "content": "30kW."},
        {"role": "assistant", "content": "Ambiente interno o esterno?"},
        {"role": "user", "content": "Interno, IP54."},
    ]
    assert count_clarification_exchanges(messages) == 3


def test_count_exchanges_assistant_asked_no_reply():
    messages = [
        {"role": "user", "content": "Impianto."},
        {"role": "assistant", "content": "Qual e la tensione?"},
    ]
    assert count_clarification_exchanges(messages) == 0


def test_count_exchanges_list_content():
    messages = [
        {"role": "user", "content": "Impianto."},
        {"role": "assistant", "content": [{"type": "text", "text": "Qual e la tensione?"}]},
        {"role": "user", "content": "400V."},
    ]
    assert count_clarification_exchanges(messages) == 1


# ─── has_clarifications_been_asked ─────────────────────────────────────────

def test_no_clarifications_asked_empty_history():
    assert has_clarifications_been_asked([]) is False


def test_no_clarifications_asked_only_user_messages():
    messages = [{"role": "user", "content": "Voglio installare un impianto."}]
    assert has_clarifications_been_asked(messages) is False


def test_one_exchange_not_enough():
    messages = [
        {"role": "user", "content": "Impianto."},
        {"role": "assistant", "content": "Qual e la tensione?"},
        {"role": "user", "content": "400V."},
    ]
    assert has_clarifications_been_asked(messages) is False


def test_two_exchanges_not_enough():
    messages = [
        {"role": "user", "content": "Impianto."},
        {"role": "assistant", "content": "Qual e la tensione?"},
        {"role": "user", "content": "400V."},
        {"role": "assistant", "content": "Qual e la potenza?"},
        {"role": "user", "content": "30kW."},
    ]
    assert has_clarifications_been_asked(messages) is False


def test_three_exchanges_sufficient():
    messages = [
        {"role": "user", "content": "Impianto industriale."},
        {"role": "assistant", "content": "Qual e la tensione?"},
        {"role": "user", "content": "400V."},
        {"role": "assistant", "content": "Qual e la potenza?"},
        {"role": "user", "content": "30kW."},
        {"role": "assistant", "content": "Ambiente interno o esterno?"},
        {"role": "user", "content": "Interno, IP54."},
    ]
    assert has_clarifications_been_asked(messages) is True


def test_has_clarifications_handles_list_content():
    messages = [
        {"role": "user", "content": "Impianto."},
        {"role": "assistant", "content": [{"type": "text", "text": "Tensione?"}]},
        {"role": "user", "content": "400V."},
        {"role": "assistant", "content": [{"type": "text", "text": "Potenza?"}]},
        {"role": "user", "content": "30kW."},
        {"role": "assistant", "content": [{"type": "text", "text": "Ambiente?"}]},
        {"role": "user", "content": "Interno."},
    ]
    assert has_clarifications_been_asked(messages) is True


def test_has_clarifications_list_content_no_question():
    messages = [
        {"role": "assistant", "content": [{"type": "text", "text": "Certo, capito."}]},
    ]
    assert has_clarifications_been_asked(messages) is False


# ─── detect_domain ──────────────────────────────────────────────────────────

def test_detect_domain_elettrico():
    messages = [
        {"role": "user", "content": "Devo installare un impianto con tensione 400V trifase e interruttore differenziale."},
    ]
    assert detect_domain(messages) == "elettrico"


def test_detect_domain_idraulico():
    messages = [
        {"role": "user", "content": "Ho una pompa idraulica con pressione di 200 bar e un cilindro."},
    ]
    assert detect_domain(messages) == "idraulico"


def test_detect_domain_pneumatico():
    messages = [
        {"role": "user", "content": "Schema pneumatico con aria compressa e cilindro pneumatico."},
    ]
    assert detect_domain(messages) == "pneumatico"


def test_detect_domain_plc():
    messages = [
        {"role": "user", "content": "Devo programmare un PLC Siemens con Profinet."},
    ]
    assert detect_domain(messages) == "plc"


def test_detect_domain_generale_fallback():
    messages = [
        {"role": "user", "content": "Buongiorno, ho bisogno di aiuto."},
    ]
    assert detect_domain(messages) == "generale"


def test_detect_domain_empty():
    assert detect_domain([]) == "generale"


# ─── build_system_prompt ────────────────────────────────────────────────────

def test_build_system_prompt_technical_no_clarifications():
    prompt = build_system_prompt(is_technical=True, clarifications_asked=False)
    assert "domande di chiarimento" in prompt.lower() or "ISTRUZIONE PRIORITARIA" in prompt


def test_build_system_prompt_technical_clarifications_done():
    prompt = build_system_prompt(is_technical=True, clarifications_asked=True)
    assert "ISTRUZIONE PRIORITARIA" not in prompt


def test_build_system_prompt_non_technical():
    prompt = build_system_prompt(is_technical=False, clarifications_asked=False)
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert "ISTRUZIONE PRIORITARIA" not in prompt


def test_build_system_prompt_uses_domain_instruction_elettrico():
    messages = [{"role": "user", "content": "Impianto elettrico con tensione 400V trifase e interruttore."}]
    prompt = build_system_prompt(is_technical=True, clarifications_asked=False, messages=messages)
    assert "ISTRUZIONE PRIORITARIA" in prompt
    assert "tensione" in prompt.lower()


def test_build_system_prompt_uses_domain_instruction_plc():
    messages = [{"role": "user", "content": "Devo installare un PLC con Profinet e moduli IO."}]
    prompt = build_system_prompt(is_technical=True, clarifications_asked=False, messages=messages)
    assert "ISTRUZIONE PRIORITARIA" in prompt
    assert "PLC" in prompt or "plc" in prompt.lower()


def test_build_system_prompt_with_search_context():
    context = "=== Contesto da ricerca web ===\nRisultato fittizio"
    prompt = build_system_prompt(is_technical=False, clarifications_asked=False, search_context=context)
    assert "Contesto da ricerca web" in prompt


def test_build_system_prompt_empty_search_context():
    prompt_no_ctx = build_system_prompt(is_technical=False, clarifications_asked=False)
    prompt_empty = build_system_prompt(is_technical=False, clarifications_asked=False, search_context="")
    assert prompt_no_ctx == prompt_empty


def test_build_system_prompt_messages_param_ignored_if_clarifications_done():
    messages = [{"role": "user", "content": "Tensione 400V."}]
    prompt = build_system_prompt(is_technical=True, clarifications_asked=True, messages=messages)
    assert "ISTRUZIONE PRIORITARIA" not in prompt


# ─── should_search ──────────────────────────────────────────────────────────

def test_should_search_normativa():
    assert should_search("Qual e la normativa CEI per impianti BT?") is True


def test_should_search_prezzo():
    assert should_search("Qual e il prezzo di un interruttore Legrand?") is True


def test_should_search_scheda_tecnica():
    assert should_search("Dammi la scheda tecnica del motore ABB") is True


def test_should_search_no_trigger():
    assert should_search("Come collegare due cavi insieme?") is False
