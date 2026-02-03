from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from bs4 import BeautifulSoup

from src.utils.hashing import sha256_text
from src.utils.time import safe_datetime


@dataclass
class ItemData:
    source_id: str
    title: str
    content_text: str
    url: Optional[str]
    published_at: Optional[datetime]
    ingested_at: datetime
    links: List[str]
    fingerprint: str


def clean_text(text: str, strip_whitespace: bool = True) -> str:
    if strip_whitespace:
        return " ".join(text.split())
    return text


def extract_links_from_html(html: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for link in soup.find_all("a"):
        href = link.get("href")
        if href:
            links.append(href)
    return list(dict.fromkeys(links))


def normalise_from_rss(source_id: str, entry: dict, use_entry_published_date: bool) -> ItemData:
    title = entry.get("title", "")
    url = entry.get("link")
    content = ""
    if entry.get("content"):
        content = entry["content"][0].get("value", "")
    elif entry.get("summary"):
        content = entry.get("summary", "")

    links = extract_links_from_html(content)
    soup = BeautifulSoup(content, "html.parser")
    content_text = clean_text(soup.get_text(" "))

    published_at = None
    if use_entry_published_date:
        published_at = entry.get("published_parsed")
        if published_at:
            published_at = datetime(*published_at[:6], tzinfo=timezone.utc)

    fingerprint = sha256_text(url or f"{title}:{content_text[:500]}")

    return ItemData(
        source_id=source_id,
        title=title,
        content_text=content_text,
        url=url,
        published_at=published_at,
        ingested_at=safe_datetime(None),
        links=links,
        fingerprint=fingerprint,
    )


def normalise_from_website(
    source_id: str,
    url: str,
    title: str,
    content_text: str,
    links: List[str],
) -> ItemData:
    fingerprint = sha256_text(url or f"{title}:{content_text[:500]}")
    return ItemData(
        source_id=source_id,
        title=title,
        content_text=content_text,
        url=url,
        published_at=None,
        ingested_at=safe_datetime(None),
        links=links,
        fingerprint=fingerprint,
    )


def normalise_from_gmail(
    source_id: str,
    subject: str,
    body_text: str,
    links: List[str],
    message_id: str,
) -> ItemData:
    fingerprint = sha256_text(message_id or f"{subject}:{body_text[:500]}")
    return ItemData(
        source_id=source_id,
        title=subject,
        content_text=body_text,
        url=None,
        published_at=None,
        ingested_at=safe_datetime(None),
        links=links,
        fingerprint=fingerprint,
    )
