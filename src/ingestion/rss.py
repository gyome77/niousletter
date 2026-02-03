from __future__ import annotations

import logging
from typing import List

import feedparser

from src.ingestion.normalise import ItemData, normalise_from_rss

logger = logging.getLogger(__name__)


def poll_rss(source_id: str, feed_url: str, use_entry_published_date: bool) -> List[ItemData]:
    parsed = feedparser.parse(feed_url)
    items: List[ItemData] = []
    for entry in parsed.entries:
        try:
            items.append(normalise_from_rss(source_id, entry, use_entry_published_date))
        except Exception:
            logger.exception("Failed to normalise RSS entry", extra={"source_id": source_id})
    return items
