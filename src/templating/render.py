from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.tracking.tokens import build_token


def create_env(template_dir: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )


def render_newsletter(
    template_dir: Path,
    template_html: str,
    template_text: str,
    data: Dict[str, Any],
) -> tuple[str, str]:
    env = create_env(template_dir)
    html_tpl = env.get_template(template_html)
    text_tpl = env.get_template(template_text)
    return html_tpl.render(**data), text_tpl.render(**data)


def prepare_render_data(
    newsletter: Dict[str, Any],
    period: Dict[str, Any],
    recipient: Dict[str, Any],
    items: List[Dict[str, Any]],
    run_id: int,
    app_base_url: str,
    tracking_secret: str,
    open_tracking: bool,
    click_tracking: bool,
    include_links: bool = True,
) -> Dict[str, Any]:
    all_links = []
    for item in items:
        all_links.extend(item.get("links", []))

    all_links = list(dict.fromkeys(all_links))
    if not include_links:
        all_links = []

    if click_tracking:
        tracked_links = []
        for link in all_links:
            token = build_token(tracking_secret, recipient["email"], run_id, link)
            encoded = quote(link, safe="")
            tracked_links.append(f"{app_base_url}/t/click/{token}?u={encoded}")
        all_links = tracked_links

    open_pixel = None
    if open_tracking:
        token = build_token(tracking_secret, recipient["email"], run_id, None)
        open_pixel = f"{app_base_url}/t/open/{token}.png"

    unsubscribe_token = build_token(tracking_secret, recipient["email"], run_id, "unsubscribe")
    unsubscribe_url = f"{app_base_url}/unsubscribe/{unsubscribe_token}"

    return {
        "newsletter": newsletter,
        "period": period,
        "recipient": recipient,
        "items": items,
        "all_links": all_links,
        "meta": {"run_id": run_id, "generated_at": datetime.utcnow().isoformat()},
        "open_tracking_pixel": open_pixel,
        "unsubscribe_url": unsubscribe_url,
    }
