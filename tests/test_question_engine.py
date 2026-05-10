from services.question_engine import detect_technical_request, has_clarifications_been_asked, build_system_prompt, should_search


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
    assert "ISTRUZIONE PRIORITARIA" not in prompt


def test_build_system_prompt_non_technical():
    prompt = build_system_prompt(is_technical=False, clarifications_asked=False)
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert "ISTRUZIONE PRIORITARIA" not in prompt


def test_has_clarifications_handles_list_content():
    messages = [
        {"role": "assistant", "content": [{"type": "text", "text": "Qual è la tensione?"}]},
    ]
    assert has_clarifications_been_asked(messages) is True


def test_has_clarifications_list_content_no_question():
    messages = [
        {"role": "assistant", "content": [{"type": "text", "text": "Certo, capito."}]},
    ]
    assert has_clarifications_been_asked(messages) is False


def test_should_search_normativa():
    assert should_search("Qual è la normativa CEI per impianti BT?") is True


def test_should_search_prezzo():
    assert should_search("Qual è il prezzo di un interruttore Legrand?") is True


def test_should_search_scheda_tecnica():
    assert should_search("Dammi la scheda tecnica del motore ABB") is True


def test_should_search_no_trigger():
    assert should_search("Come collegare due cavi insieme?") is False


def test_build_system_prompt_with_search_context():
    context = "=== Contesto da ricerca web ===\nRisultato fittizio"
    prompt = build_system_prompt(is_technical=False, clarifications_asked=False, search_context=context)
    assert "Contesto da ricerca web" in prompt


def test_build_system_prompt_empty_search_context():
    prompt_no_ctx = build_system_prompt(is_technical=False, clarifications_asked=False)
    prompt_empty = build_system_prompt(is_technical=False, clarifications_asked=False, search_context="")
    assert prompt_no_ctx == prompt_empty
