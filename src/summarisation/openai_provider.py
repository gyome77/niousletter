from __future__ import annotations

import requests

from src.summarisation.prompts import SUMMARY_SYSTEM, SUMMARY_TEMPLATE
from src.summarisation.provider import SummaryProvider, SummaryRequest


class OpenAIProvider(SummaryProvider):
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model
        self.name = f"openai:{model}"

    def summarize(self, request: SummaryRequest) -> str:
        prompt = SUMMARY_TEMPLATE.format(
            style=request.style,
            length=request.length,
            tone=request.tone,
            language=request.language,
            content=request.content,
        )
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SUMMARY_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
