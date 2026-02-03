from __future__ import annotations

from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from src.db.models import EmailSent, Event, NewsletterRunItem, Item
from src.db.session import get_session
from src.tracking.tokens import verify_token

router = APIRouter()


def is_allowed_link(session, run_id: int, link: str) -> bool:
    items = (
        session.query(Item)
        .join(NewsletterRunItem, NewsletterRunItem.item_id == Item.id)
        .filter(NewsletterRunItem.run_id == run_id)
        .all()
    )
    allowed = set()
    for item in items:
        if item.links:
            allowed.update(item.links)
        if item.url:
            allowed.add(item.url)
    return link in allowed


@router.get("/t/click/{token}")
def track_click(request: Request, token: str, u: str):
    secret = request.app.state.settings.tracking_token_secret
    payload = verify_token(secret, token)
    if not payload:
        raise HTTPException(status_code=400, detail="Invalid token")

    target = unquote(u)

    with get_session() as session:
        if not is_allowed_link(session, payload["run_id"], target):
            raise HTTPException(status_code=400, detail="Invalid target")

        email = (
            session.query(EmailSent)
            .filter(EmailSent.run_id == payload["run_id"], EmailSent.recipient_email == payload["email"])
            .first()
        )
        if email:
            event = Event(email_id=email.id, type="click", link_url=target)
            session.add(event)
            session.commit()

    return RedirectResponse(target)
