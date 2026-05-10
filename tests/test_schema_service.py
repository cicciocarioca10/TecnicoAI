import pytest
from unittest.mock import patch, AsyncMock
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
    from unittest.mock import MagicMock, AsyncMock

    mock_db = MagicMock()
    mock_msg = MagicMock()
    mock_msg.role = "user"
    mock_msg.content = "Crea un circuito di sicurezza."  # no keywords -> normally svg
    mock_schema = MagicMock()
    mock_schema.id = 5

    with patch("db.database.get_messages", new_callable=AsyncMock, return_value=[mock_msg]):
        with patch("services.schema_service.send_message", new_callable=AsyncMock, return_value="digraph schema { A -> B }"):
            with patch("services.schema_service.render_to_pdf", return_value=b"%PDF"):
                with patch("db.database.create_schema", new_callable=AsyncMock, return_value=mock_schema):
                    with patch("builtins.open", MagicMock()):
                        with patch("os.makedirs"):
                            result = await generate_schema(1, mock_db, domain="safety", model="claude")

    assert result["engine"] == "graphviz"  # forced by safety domain
    assert result["schema_id"] == 5
