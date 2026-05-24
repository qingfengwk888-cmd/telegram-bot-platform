from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.config import BASE_URL, PLATFORM_BOT_TOKEN
from app.core.logger import logger
from app.telegram.api import set_telegram_http_client, tg


@asynccontextmanager
async def lifespan(app: FastAPI):
    telegram_http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )
    set_telegram_http_client(telegram_http_client)

    try:
        if PLATFORM_BOT_TOKEN and BASE_URL:
            webhook_url = f"{BASE_URL.rstrip('/')}/platform/webhook"
            try:
                result = await tg(PLATFORM_BOT_TOKEN, "setWebhook", {
                    "url": webhook_url,
                    "drop_pending_updates": False,
                })
                logger.info("platform webhook setup result: %s", result)
            except Exception:
                logger.exception("platform webhook setup failed")

        yield

    finally:
        try:
            await telegram_http_client.aclose()
        finally:
            set_telegram_http_client(None)
