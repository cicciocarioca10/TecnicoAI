import os
import pytest
from unittest.mock import MagicMock, patch

from services.ai_service import send_message


SAMPLE_MESSAGES = [
    {"role": "user", "content": "Ciao, ho bisogno di aiuto."}
]


@pytest.mark.asyncio
async def test_send_message_claude_returns_string():
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="Risposta di test")]
    mock_client = MagicMock()
    mock_client.messages.create = MagicMock(return_value=mock_message)

    with patch("services.ai_service.anthropic.Anthropic", return_value=mock_client):
        with patch.dict(os.environ, {"CLAUDE_API_KEY": "test-key", "AI_MODEL": "claude"}):
            result = await send_message(SAMPLE_MESSAGES, system_prompt="Test", model="claude")

    assert isinstance(result, str)
    assert result == "Risposta di test"


@pytest.mark.asyncio
async def test_send_message_deepseek_returns_string():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Risposta DeepSeek"}}]
    }

    with patch("services.ai_service.requests.post", return_value=mock_response):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            result = await send_message(SAMPLE_MESSAGES, system_prompt="Test", model="deepseek")

    assert result == "Risposta DeepSeek"


@pytest.mark.asyncio
async def test_send_message_uses_env_default_model():
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="OK")]
    mock_client = MagicMock()
    mock_client.messages.create = MagicMock(return_value=mock_message)

    with patch("services.ai_service.anthropic.Anthropic", return_value=mock_client):
        with patch.dict(os.environ, {"CLAUDE_API_KEY": "key", "AI_MODEL": "claude"}):
            result = await send_message(SAMPLE_MESSAGES, system_prompt="Test")

    assert result == "OK"


@pytest.mark.asyncio
async def test_send_message_raises_on_unknown_model():
    with pytest.raises(ValueError, match="Modello non supportato"):
        await send_message(SAMPLE_MESSAGES, system_prompt="Test", model="gpt-99")


@pytest.mark.asyncio
async def test_send_message_raises_on_missing_claude_key():
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("CLAUDE_API_KEY", None)
        with pytest.raises(ValueError, match="CLAUDE_API_KEY"):
            await send_message(SAMPLE_MESSAGES, system_prompt="Test", model="claude")


@pytest.mark.asyncio
async def test_send_message_raises_on_missing_deepseek_key():
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("DEEPSEEK_API_KEY", None)
        with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
            await send_message(SAMPLE_MESSAGES, system_prompt="Test", model="deepseek")


@pytest.mark.asyncio
async def test_deepseek_calls_raise_for_status():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "OK"}}]
    }
    with patch("services.ai_service.requests.post", return_value=mock_response):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            await send_message(SAMPLE_MESSAGES, system_prompt="Test", model="deepseek")
    mock_response.raise_for_status.assert_called_once()


@pytest.mark.asyncio
async def test_send_message_claude_with_image():
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="Vedo un interruttore.")]
    mock_client = MagicMock()
    mock_client.messages.create = MagicMock(return_value=mock_message)

    with patch("services.ai_service.anthropic.Anthropic", return_value=mock_client):
        with patch.dict(os.environ, {"CLAUDE_API_KEY": "test-key"}):
            result = await send_message(
                SAMPLE_MESSAGES,
                system_prompt="Test",
                model="claude",
                image_base64="dGVzdA==",
                image_type="image/jpeg",
            )

    assert result == "Vedo un interruttore."
    call_args = mock_client.messages.create.call_args
    last_msg = call_args.kwargs["messages"][-1]
    assert isinstance(last_msg["content"], list)
    assert last_msg["content"][0]["type"] == "image"
    assert last_msg["content"][0]["source"]["data"] == "dGVzdA=="
    assert last_msg["content"][1]["type"] == "text"


@pytest.mark.asyncio
async def test_send_message_deepseek_with_image_adds_note():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Risposta con nota"}}]
    }

    with patch("services.ai_service.requests.post", return_value=mock_response) as mock_post:
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            await send_message(
                SAMPLE_MESSAGES,
                system_prompt="Test",
                model="deepseek",
                image_base64="dGVzdA==",
            )

    payload = mock_post.call_args.kwargs["json"]
    last_user_msg = [m for m in payload["messages"] if m["role"] == "user"][-1]
    assert "analisi non disponibile" in last_user_msg["content"]
