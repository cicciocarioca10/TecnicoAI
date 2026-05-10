import asyncio
import os

import anthropic
import requests


CLAUDE_MODEL = "claude-sonnet-4-20250514"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


async def send_message(
    messages: list[dict],
    system_prompt: str,
    model: str | None = None,
) -> str:
    if model is None:
        model = os.getenv("AI_MODEL", "claude")

    if model == "claude":
        return await asyncio.to_thread(_send_claude, messages, system_prompt)
    elif model == "deepseek":
        return await asyncio.to_thread(_send_deepseek, messages, system_prompt)
    else:
        raise ValueError(f"Modello non supportato: {model}")


def _send_claude(messages: list[dict], system_prompt: str) -> str:
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        raise ValueError("CLAUDE_API_KEY non configurata")
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=messages,
    )
    if not response.content:
        raise RuntimeError("Risposta Claude vuota o malformata")
    return response.content[0].text


def _send_deepseek(messages: list[dict], system_prompt: str) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY non configurata")
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "system", "content": system_prompt}] + messages,
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
