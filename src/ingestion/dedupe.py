from __future__ import annotations

from typing import Iterable, List, Set

from src.ingestion.normalise import ItemData


def dedupe_items(items: Iterable[ItemData]) -> List[ItemData]:
    seen: Set[str] = set()
    result: List[ItemData] = []
    for item in items:
        key = f"{item.source_id}:{item.fingerprint}"
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
