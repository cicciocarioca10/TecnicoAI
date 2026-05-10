import asyncio
import os
from typing import Optional

import anthropic
import requests


CLAUDE_MODEL = "claude-sonnet-4-20250514"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


async def send_message(
    messages: list[dict],
    system_prompt: str,
    model: str | None = None,
    image_base64: Optional[str] = None,
    image_type: str = "image/jpeg",
) -> str:
    if model is None:
        model = os.getenv("AI_MODEL", "claude")

    if model == "claude":
        return await asyncio.to_thread(_send_claude, messages, system_prompt, image_base64, image_type)
    elif model == "deepseek":
        return await asyncio.to_thread(_send_deepseek, messages, system_prompt, image_base64)
    else:
        raise ValueError(f"Modello non supportato: {model}")


def _send_claude(
    messages: list[dict],
    system_prompt: str,
    image_base64: Optional[str] = None,
    image_type: str = "image/jpeg",
) -> str:
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        raise ValueError("CLAUDE_API_KEY non configurata")
    client = anthropic.Anthropic(api_key=api_key)

    msgs = list(messages)
    if image_base64 and msgs and msgs[-1]["role"] == "user":
        last = msgs[-1]
        msgs[-1] = {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": image_type,
                        "data": image_base64,
                    },
                },
                {"type": "text", "text": last["content"]},
            ],
        }

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=msgs,
    )
    if not response.content:
        raise RuntimeError("Risposta Claude vuota o malformata")
    return response.content[0].text


def _send_deepseek(
    messages: list[dict],
    system_prompt: str,
    image_base64: Optional[str] = None,
) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY non configurata")

    msgs = list(messages)
    if image_base64 and msgs and msgs[-1]["role"] == "user":
        last = msgs[-1]
        msgs[-1] = {**last, "content": last["content"] + "\n[Immagine caricata - analisi non disponibile con DeepSeek]"}

    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "system", "content": system_prompt}] + msgs,
        "max_tokens": 4096,
    }
    response = requests.post(
        DEEPSEEK_API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]
