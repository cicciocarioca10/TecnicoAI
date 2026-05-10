import asyncio
import os

import requests

TAVILY_API_URL = "https://api.tavily.com/search"


def _search(query: str) -> str:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key or os.getenv("SEARCH_ENABLED", "true").lower() == "false":
        return ""
    try:
        resp = requests.post(
            TAVILY_API_URL,
            json={"api_key": api_key, "query": query, "search_depth": "basic", "max_results": 3},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])[:3]
        if not results:
            return ""
        lines = ["=== Contesto da ricerca web ==="]
        for r in results:
            title = r.get("title", "")
            content = r.get("content", "")[:300]
            url = r.get("url", "")
            lines.append(f"**{title}**\n{content}\nFonte: {url}")
        return "\n\n".join(lines)
    except Exception:
        return ""


async def search_technical_info(query: str) -> str:
    return await asyncio.to_thread(_search, query)
