from __future__ import annotations

import base64
import logging
from typing import List, Optional

from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from src.ingestion.normalise import extract_links_from_html, normalise_from_gmail

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def load_credentials(credentials_json: str, token_json: str) -> Credentials:
    creds = None
    if token_json:
        creds = Credentials.from_authorized_user_file(token_json, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_json, SCOPES)
            creds = flow.run_local_server(port=0)
        if token_json:
            with open(token_json, "w", encoding="utf-8") as handle:
                handle.write(creds.to_json())
    return creds


def get_message_body(payload: dict, parse_mode: str) -> str:
    if payload.get("parts"):
        for part in payload["parts"]:
            mime_type = part.get("mimeType", "")
            if parse_mode == "html" and mime_type == "text/html":
                return decode_body(part)
            if parse_mode == "plain" and mime_type == "text/plain":
                return decode_body(part)
    if payload.get("body"):
        return decode_body(payload)
    return ""


def decode_body(part: dict) -> str:
    body = part.get("body", {}).get("data", "")
    if not body:
        return ""
    data = base64.urlsafe_b64decode(body.encode("utf-8"))
    return data.decode("utf-8", errors="ignore")


def poll_gmail(
    source_id: str,
    credentials_json: str,
    token_json: str,
    gmail_query: str,
    allowed_senders: Optional[List[str]],
    allowed_domains: Optional[List[str]],
    parse_mode: str,
    extract_links: bool,
) -> List:
    creds = load_credentials(credentials_json, token_json)
    service = build("gmail", "v1", credentials=creds)

    response = service.users().messages().list(userId="me", q=gmail_query).execute()
    messages = response.get("messages", [])

    items = []
    for message in messages:
        msg = service.users().messages().get(userId="me", id=message["id"], format="full").execute()
        headers = msg.get("payload", {}).get("headers", [])
        header_map = {h["name"].lower(): h["value"] for h in headers}
        from_header = header_map.get("from", "")
        subject = header_map.get("subject", "(no subject)")

        if allowed_senders and not any(sender in from_header for sender in allowed_senders):
            continue
        if allowed_domains and not any(domain in from_header for domain in allowed_domains):
            continue

        body = get_message_body(msg.get("payload", {}), parse_mode=parse_mode)
        if parse_mode == "html":
            soup = BeautifulSoup(body, "html.parser")
            text_body = " ".join(soup.get_text(" ").split())
            links = extract_links_from_html(body) if extract_links else []
        else:
            text_body = " ".join(body.split())
            links = []

        items.append(normalise_from_gmail(source_id, subject, text_body, links, msg.get("id", "")))

    return items
