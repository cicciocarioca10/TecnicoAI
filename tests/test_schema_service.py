import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from services.schema_service import (
    build_schema_system_prompt,
    render_to_pdf,
    _extract_svg,
)


def test_build_system_prompt_svg_auto():
    prompt = build_schema_system_prompt("auto")
    assert "<svg" in prompt
    assert "viewBox" in prompt


def test_build_system_prompt_elettrico():
    prompt = build_schema_system_prompt("elettrico")
    assert "IEC 60617" in prompt


def test_build_system_prompt_plc():
    prompt = build_schema_system_prompt("plc")
    assert "PLC" in prompt
    assert "I/O" in prompt


def test_build_system_prompt_pneumatico():
    prompt = build_schema_system_prompt("pneumatico")
    assert "ISO 1219" in prompt


def test_build_system_prompt_idraulico():
    prompt = build_schema_system_prompt("idraulico")
    assert "idraulic" in prompt.lower()


def test_build_system_prompt_safety():
    prompt = build_schema_system_prompt("safety")
    assert "safety" in prompt.lower() or "SIL" in prompt


def test_build_system_prompt_fieldbus():
    prompt = build_schema_system_prompt("fieldbus")
    assert "fieldbus" in prompt.lower() or "rete" in prompt.lower()


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


def test_extract_svg_no_closing_tag():
    raw = "Ecco uno schema: <svg viewBox='0 0 100 100'><rect/>"
    result = _extract_svg(raw)
    assert result == raw.strip()


def test_render_to_pdf_dispatches_svg():
    with patch("services.schema_service._render_svg_to_pdf", return_value=b"%PDF-svg") as mock:
        result = render_to_pdf("<svg/>", "svg")
    assert result == b"%PDF-svg"
    mock.assert_called_once_with("<svg/>")


def test_render_to_pdf_unknown_engine():
    with pytest.raises(ValueError, match="Engine non supportato"):
        render_to_pdf("content", "unknown")


@pytest.mark.asyncio
async def test_generate_schema_svg_flow():
    from services.schema_service import generate_schema

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
async def test_generate_schema_plc_domain_uses_svg():
    from services.schema_service import generate_schema

    mock_db = MagicMock()
    mock_msg = MagicMock()
    mock_msg.role = "user"
    mock_msg.content = "Crea uno schema PLC con safety."
    mock_schema = MagicMock()
    mock_schema.id = 5

    with patch("db.database.get_messages", new_callable=AsyncMock, return_value=[mock_msg]):
        with patch("services.schema_service.send_message", new_callable=AsyncMock, return_value="<svg viewBox='0 0 1123 794'><rect/></svg>"):
            with patch("services.schema_service.render_to_pdf", return_value=b"%PDF"):
                with patch("db.database.create_schema", new_callable=AsyncMock, return_value=mock_schema):
                    with patch("builtins.open", MagicMock()):
                        with patch("os.makedirs"):
                            result = await generate_schema(1, mock_db, domain="plc", model="claude")

    assert result["engine"] == "svg"
    assert result["schema_id"] == 5


@pytest.mark.asyncio
async def test_generate_schema_safety_domain_uses_svg():
    from services.schema_service import generate_schema

    mock_db = MagicMock()
    mock_msg = MagicMock()
    mock_msg.role = "user"
    mock_msg.content = "Circuito di sicurezza SIL2."
    mock_schema = MagicMock()
    mock_schema.id = 7

    with patch("db.database.get_messages", new_callable=AsyncMock, return_value=[mock_msg]):
        with patch("services.schema_service.send_message", new_callable=AsyncMock, return_value="<svg viewBox='0 0 1123 794'><rect/></svg>"):
            with patch("services.schema_service.render_to_pdf", return_value=b"%PDF"):
                with patch("db.database.create_schema", new_callable=AsyncMock, return_value=mock_schema):
                    with patch("builtins.open", MagicMock()):
                        with patch("os.makedirs"):
                            result = await generate_schema(1, mock_db, domain="safety", model="claude")

    assert result["engine"] == "svg"
