from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from src.logging_conf import configure_logging
from src.settings import load_settings
from src.db.session import init_engine
from src.tracking.click import router as click_router
from src.tracking.open import router as open_router
from src.tracking.unsubscribe import router as unsubscribe_router


def create_app() -> FastAPI:
    settings = load_settings()
    configure_logging()
    init_engine(settings.db_url)

    app = FastAPI()
    app.state.settings = settings

    app.include_router(open_router)
    app.include_router(click_router)
    app.include_router(unsubscribe_router)

    return app


app = create_app()


if __name__ == "__main__":
    settings = load_settings()
    uvicorn.run("src.app:app", host=settings.tracking_host, port=settings.tracking_port, reload=False)
