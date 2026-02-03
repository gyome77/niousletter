from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Optional


DEFAULT_EXPIRY_SECONDS = 60 * 60 * 24 * 40  # 40 days


def build_token(secret: str, email: str, run_id: int, link: Optional[str]) -> str:
    payload = {
        "email": email,
        "run_id": run_id,
        "link": link,
        "exp": int(time.time()) + DEFAULT_EXPIRY_SECONDS,
    }
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), data, hashlib.sha256).digest()
    token = base64.urlsafe_b64encode(data + sig).decode("utf-8")
    return token


def verify_token(secret: str, token: str) -> Optional[dict]:
    try:
        raw = base64.urlsafe_b64decode(token.encode("utf-8"))
        data = raw[:-32]
        sig = raw[-32:]
        expected = hmac.new(secret.encode("utf-8"), data, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(data.decode("utf-8"))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None
