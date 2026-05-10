import os
import pytest
from unittest.mock import MagicMock, patch

from services.search_service import search_technical_info


@pytest.mark.asyncio
async def test_search_returns_empty_without_api_key():
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("TAVILY_API_KEY", None)
        result = await search_technical_info("normativa CEI 64-8")
    assert result == ""


@pytest.mark.asyncio
async def test_search_returns_empty_when_disabled():
    with patch.dict(os.environ, {"TAVILY_API_KEY": "key", "SEARCH_ENABLED": "false"}):
        result = await search_technical_info("normativa CEI 64-8")
    assert result == ""


@pytest.mark.asyncio
async def test_search_returns_formatted_results():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "results": [
            {"title": "CEI 64-8", "content": "Norma per impianti elettrici", "url": "https://example.com/1"},
            {"title": "IEC 60364", "content": "Electrical installations", "url": "https://example.com/2"},
        ]
    }

    with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}):
        with patch("services.search_service.requests.post", return_value=mock_resp):
            result = await search_technical_info("normativa CEI")

    assert "Contesto da ricerca web" in result
    assert "CEI 64-8" in result
    assert "IEC 60364" in result
    mock_resp.raise_for_status.assert_called_once()


@pytest.mark.asyncio
async def test_search_returns_max_3_results():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "results": [
            {"title": f"Result {i}", "content": f"Content {i}", "url": f"https://example.com/{i}"}
            for i in range(5)
        ]
    }

    with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}):
        with patch("services.search_service.requests.post", return_value=mock_resp):
            result = await search_technical_info("CEI")

    assert result.count("Fonte:") == 3


@pytest.mark.asyncio
async def test_search_silent_on_error():
    with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}):
        with patch("services.search_service.requests.post", side_effect=ConnectionError("timeout")):
            result = await search_technical_info("CEI")
    assert result == ""


@pytest.mark.asyncio
async def test_search_returns_empty_on_no_results():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": []}

    with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}):
        with patch("services.search_service.requests.post", return_value=mock_resp):
            result = await search_technical_info("qualcosa")
    assert result == ""
