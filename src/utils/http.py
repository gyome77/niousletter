from __future__ import annotations

import logging
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def get_text(url: str, timeout: int = 20, headers: Optional[dict] = None) -> str:
    response = requests.get(url, timeout=timeout, headers=headers)
    response.raise_for_status()
    return response.text
