import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from services.schema_service import (
    detect_complexity,
    build_schema_system_prompt,
    render_to_pdf,
    _extract_svg,
    _extract_dot,
    _sanitize_dot,
    _validate_dot,
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


def test_detect_complexity_empty_messages():
    assert detect_complexity([]) == "svg"


def test_detect_complexity_ignores_assistant_messages():
    messages = [
        {"role": "user", "content": "Come collegare un interruttore?"},
        {"role": "assistant", "content": "Risposta con menzione di PLC e robot per confronto."},
    ]
    assert detect_complexity(messages) == "svg"


def test_extract_svg_no_closing_tag():
    raw = "Ecco uno schema: <svg viewBox='0 0 100 100'><rect/>"
    result = _extract_svg(raw)
    assert result == raw.strip()


def test_extract_dot_no_closing_brace():
    raw = "digraph schema { A -> B"
    result = _extract_dot(raw)
    assert result == raw.strip()


def test_sanitize_dot_removes_non_ascii():
    dot = 'digraph { A [label="Motore – principale"] }'
    result = _sanitize_dot(dot)
    assert '\xe2' not in result
    assert '\x80' not in result
    assert '\x93' not in result
    assert 'Motore' in result
    assert 'principale' in result


def test_sanitize_dot_escapes_unescaped_quotes():
    dot = 'digraph { A [label="He said "hello" here"] }'
    result = _sanitize_dot(dot)
    assert '\\"hello\\"' in result or 'hello' in result


def test_sanitize_dot_adds_semicolons():
    dot = 'digraph {\n  A -> B\n  B -> C\n}'
    result = _sanitize_dot(dot)
    lines = [l.rstrip() for l in result.splitlines() if l.strip() and l.strip() not in ('{', '}')]
    for line in lines:
        assert line.endswith(';') or line.endswith('{') or line.endswith('}')


def test_sanitize_dot_preserves_valid_code():
    dot = 'digraph schema {\n  A -> B;\n  B [label="test"];\n}'
    result = _sanitize_dot(dot)
    assert 'A -> B' in result
    assert 'test' in result


def test_validate_dot_returns_true_if_dot_missing():
    with patch("subprocess.run", side_effect=FileNotFoundError):
        valid, msg = _validate_dot("digraph { A -> B }")
    assert valid is True
    assert msg == ""


def test_validate_dot_returns_false_on_timeout():
    import subprocess
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd='dot', timeout=30)):
        valid, msg = _validate_dot("digraph { A -> B }")
    assert valid is False
    assert "Timeout" in msg


def test_validate_dot_returns_true_on_success():
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result):
        valid, msg = _validate_dot("digraph { A -> B }")
    assert valid is True
    assert msg == ""


def test_validate_dot_returns_false_on_error():
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "syntax error in line 1"
    with patch("subprocess.run", return_value=mock_result):
        valid, msg = _validate_dot("bad dot")
    assert valid is False
    assert "syntax error" in msg


@pytest.mark.asyncio
async def test_generate_schema_svg_flow():
    from services.schema_service import generate_schema
    from unittest.mock import MagicMock, AsyncMock

    mock_db = MagicMock()
    mock_msg = MagicMock()
    mock_msg.role = "user"
    mock_msg.content = "Come collegare un interruttore?"
    mock_schema = MagicMock()
    mock_schema.id = 42

    with patch("db.database.get_messages", new_callable=AsyncMock, return_value=[mock_msg]):
        with patch("services.schema_service.send_message", new_callable=AsyncMock, return_value="<svg viewBox='0 0 1123 794'><rect/></svg>"):
            with patch("services.schema_service.render_to_pdf", return_value=b"%PDF"):
                with patch("db.database.create_schema", new_callable=AsyncMock, return_value=mock_schema):
                    with patch("builtins.open", MagicMock()):
                        with patch("os.makedirs"):
                            result = await generate_schema(1, mock_db, domain="auto", model="claude")

    assert result["schema_id"] == 42
    assert result["engine"] == "svg"
    assert result["pdf_url"] == "/api/schema/pdf/42"
    assert "<svg" in result["content"]


@pytest.mark.asyncio
async def test_generate_schema_graphviz_domain_override():
    from services.schema_service import generate_schema

    mock_db = MagicMock()
    mock_msg = MagicMock()
    mock_msg.role = "user"
    mock_msg.content = "Crea un circuito di sicurezza."
    mock_schema = MagicMock()
    mock_schema.id = 5

    with patch("db.database.get_messages", new_callable=AsyncMock, return_value=[mock_msg]):
        with patch("services.schema_service.send_message", new_callable=AsyncMock, return_value="digraph schema { A -> B }"):
            with patch("services.schema_service._validate_dot", return_value=(True, "")):
                with patch("services.schema_service.render_to_pdf", return_value=b"%PDF"):
                    with patch("db.database.create_schema", new_callable=AsyncMock, return_value=mock_schema):
                        with patch("builtins.open", MagicMock()):
                            with patch("os.makedirs"):
                                result = await generate_schema(1, mock_db, domain="safety", model="claude")

    assert result["engine"] == "graphviz"
    assert result["schema_id"] == 5


@pytest.mark.asyncio
async def test_generate_schema_dot_retry_on_invalid():
    from services.schema_service import generate_schema

    mock_db = MagicMock()
    mock_msg = MagicMock()
    mock_msg.role = "user"
    mock_msg.content = "Schema PLC."
    mock_schema = MagicMock()
    mock_schema.id = 7

    send_calls = 0

    async def mock_send(messages, **kwargs):
        nonlocal send_calls
        send_calls += 1
        return "digraph schema { A -> B }"

    validate_results = [(False, "syntax error line 1"), (True, "")]
    validate_idx = 0

    def mock_validate(dot_code):
        nonlocal validate_idx
        result = validate_results[validate_idx]
        validate_idx += 1
        return result

    with patch("db.database.get_messages", new_callable=AsyncMock, return_value=[mock_msg]):
        with patch("services.schema_service.send_message", side_effect=mock_send):
            with patch("services.schema_service._validate_dot", side_effect=mock_validate):
                with patch("services.schema_service.render_to_pdf", return_value=b"%PDF"):
                    with patch("db.database.create_schema", new_callable=AsyncMock, return_value=mock_schema):
                        with patch("builtins.open", MagicMock()):
                            with patch("os.makedirs"):
                                result = await generate_schema(1, mock_db, domain="plc", model="claude")

    assert send_calls == 2
    assert result["engine"] == "graphviz"
    assert result["schema_id"] == 7
