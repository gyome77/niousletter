from __future__ import annotations

from datetime import datetime
from typing import Dict


def score_item(published_at: datetime | None, source_type: str, weights: Dict[str, float]) -> float:
    base = published_at.timestamp() if published_at else 0.0
    weight = weights.get(source_type, 1.0)
    return base * weight
