from __future__ import annotations

import requests

from src.summarisation.prompts import SUMMARY_TEMPLATE
from src.summarisation.provider import SummaryProvider, SummaryRequest


class OllamaProvider(SummaryProvider):
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.name = f"ollama:{model}"

    def summarize(self, request: SummaryRequest) -> str:
        prompt = SUMMARY_TEMPLATE.format(
            style=request.style,
            length=request.length,
            tone=request.tone,
            language=request.language,
            content=request.content,
        )
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False},
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()
