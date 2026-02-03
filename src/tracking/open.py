from __future__ import annotations

import base64
from fastapi import APIRouter, Request, Response

from src.db.models import EmailSent, Event
from src.db.session import get_session
from src.tracking.tokens import verify_token

router = APIRouter()

PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+o3X8AAAAASUVORK5CYII="
)


@router.get("/t/open/{token}.png")
def track_open(request: Request, token: str):
    secret = request.app.state.settings.tracking_token_secret
    payload = verify_token(secret, token)
    if payload:
        with get_session() as session:
            email = (
                session.query(EmailSent)
                .filter(EmailSent.run_id == payload["run_id"], EmailSent.recipient_email == payload["email"])
                .first()
            )
            if email:
                event = Event(email_id=email.id, type="open")
                session.add(event)
                session.commit()

    return Response(content=PIXEL, media_type="image/png")
