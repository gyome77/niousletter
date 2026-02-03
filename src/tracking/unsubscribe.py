from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.db.models import User
from src.db.session import get_session
from src.tracking.tokens import verify_token

router = APIRouter()


@router.get("/unsubscribe/{token}")
def unsubscribe(request: Request, token: str):
    secret = request.app.state.settings.tracking_token_secret
    payload = verify_token(secret, token)
    if payload:
        with get_session() as session:
            user = session.query(User).filter(User.email == payload["email"]).first()
            if user:
                user.unsubscribed = True
                session.commit()

    return HTMLResponse("<html><body><h3>You have been unsubscribed.</h3></body></html>")
