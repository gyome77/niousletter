from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class SummaryRequest:
    style: str
    length: str
    tone: str
    language: str
    content: str


class SummaryProvider(Protocol):
    name: str

    def summarize(self, request: SummaryRequest) -> str:
        ...


def length_to_sentences(length: str) -> int:
    if length == "short":
        return 2
    if length == "long":
        return 6
    return 4


def simple_summarize(request: SummaryRequest) -> str:
    sentences = request.content.split(".")
    count = length_to_sentences(request.length)
    picked = ".".join([s.strip() for s in sentences if s.strip()][:count])
    return picked.strip()
