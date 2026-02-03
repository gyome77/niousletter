from __future__ import annotations

import logging
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import List, Optional

from bs4 import BeautifulSoup

from src.ingestion.normalise import clean_text, extract_links_from_html, normalise_from_website
from src.utils.hashing import sha256_text
from src.utils.http import get_text

logger = logging.getLogger(__name__)


@dataclass
class WebsiteSnapshot:
    content_text: str
    content_hash: str


def fetch_page(url: str, fetch_method: str) -> str:
    if fetch_method == "requests":
        return get_text(url)
    if fetch_method == "playwright":
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Playwright not installed") from exc

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url, wait_until="networkidle")
            html = page.content()
            browser.close()
            return html
    raise ValueError(f"Unknown fetch_method: {fetch_method}")


def extract_content(
    html: str,
    content_css: str,
    title_css: Optional[str],
    remove_css: Optional[List[str]],
    strip_whitespace: bool,
) -> tuple[str, str, List[str]]:
    soup = BeautifulSoup(html, "html.parser")

    if remove_css:
        for selector in remove_css:
            for element in soup.select(selector):
                element.decompose()

    title = ""
    if title_css:
        title_el = soup.select_one(title_css)
        if title_el:
            title = clean_text(title_el.get_text(" "), strip_whitespace)
    if not title and soup.title:
        title = clean_text(soup.title.get_text(" "), strip_whitespace)

    content_el = soup.select_one(content_css)
    if not content_el:
        content_el = soup.body or soup

    content_text = clean_text(content_el.get_text(" "), strip_whitespace)
    links = extract_links_from_html(str(content_el))

    return title, content_text, links


def diff_ratio(old_text: str, new_text: str) -> float:
    matcher = SequenceMatcher(None, old_text, new_text)
    return 1.0 - matcher.ratio()


def detect_change(
    source_id: str,
    url: str,
    fetch_method: str,
    content_css: str,
    title_css: Optional[str],
    remove_css: Optional[List[str]],
    strip_whitespace: bool,
    change_threshold_ratio: float,
    previous_snapshot: Optional[WebsiteSnapshot],
) -> tuple[Optional[WebsiteSnapshot], Optional[dict]]:
    html = fetch_page(url, fetch_method)
    title, content_text, links = extract_content(
        html,
        content_css=content_css,
        title_css=title_css,
        remove_css=remove_css,
        strip_whitespace=strip_whitespace,
    )
    current_hash = sha256_text(content_text)
    snapshot = WebsiteSnapshot(content_text=content_text, content_hash=current_hash)

    if previous_snapshot:
        if previous_snapshot.content_hash == current_hash:
            return snapshot, None
        ratio = diff_ratio(previous_snapshot.content_text, content_text)
        if ratio < change_threshold_ratio:
            return snapshot, None

    item = normalise_from_website(
        source_id=source_id,
        url=url,
        title=title,
        content_text=content_text,
        links=links,
    )
    return snapshot, item
