from __future__ import annotations

import base64
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


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


def build_message(sender: str, recipient: str, subject: str, html_body: str, text_body: str) -> dict:
    message = MIMEMultipart("alternative")
    message["To"] = recipient
    message["From"] = sender
    message["Subject"] = subject

    message.attach(MIMEText(text_body, "plain"))
    message.attach(MIMEText(html_body, "html"))

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    return {"raw": raw}


def send_message(credentials_json: str, token_json: str, sender: str, recipient: str, subject: str, html_body: str, text_body: str) -> str:
    creds = load_credentials(credentials_json, token_json)
    service = build("gmail", "v1", credentials=creds)
    message = build_message(sender, recipient, subject, html_body, text_body)
    result = service.users().messages().send(userId="me", body=message).execute()
    return result.get("id", "")
