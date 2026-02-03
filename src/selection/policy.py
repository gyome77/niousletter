from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List

from sqlalchemy import select

from src.db.models import Item
from src.selection.ranker import score_item


def select_items(
    session,
    source_ids: List[str],
    window_days: int,
    max_items_total: int,
    per_source_limit: int | None,
    source_type_map: Dict[str, str],
    weights: Dict[str, float],
) -> List[Item]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=window_days)

    query = select(Item).where(Item.source_id.in_(source_ids)).where(Item.ingested_at >= start)
    items = session.execute(query).scalars().all()

    scored = []
    for item in items:
        source_type = source_type_map.get(item.source_id, "rss")
        scored.append((score_item(item.published_at, source_type, weights), item))

    scored.sort(key=lambda tup: tup[0], reverse=True)

    per_source_counts: Dict[str, int] = {}
    selected = []
    for _, item in scored:
        if per_source_limit is not None:
            count = per_source_counts.get(item.source_id, 0)
            if count >= per_source_limit:
                continue
        selected.append(item)
        per_source_counts[item.source_id] = per_source_counts.get(item.source_id, 0) + 1
        if len(selected) >= max_items_total:
            break

    return selected
