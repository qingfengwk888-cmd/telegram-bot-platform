import httpx
from typing import Optional

from app.core.logger import logger

telegram_http_client: Optional[httpx.AsyncClient] = None


def set_telegram_http_client(client: Optional[httpx.AsyncClient]) -> None:
    global telegram_http_client
    telegram_http_client = client

async def telegram_raw(bot_token: str, method: str, payload: dict) -> dict:
    global telegram_http_client

    if telegram_http_client is None:
        telegram_http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )

    start_ts = time.perf_counter()

    resp = await telegram_http_client.post(
        f"https://api.telegram.org/bot{bot_token}/{method}",
        json=payload,
    )
    data = resp.json()

    logger.info(
        "perf telegram_raw method=%s status_code=%s ok=%s cost_ms=%s",
        method,
        resp.status_code,
        data.get("ok"),
        cost_ms(start_ts),
    )
    return data

async def tg(bot_token: str, method: str, payload: dict) -> dict:
    data = await telegram_raw(bot_token, method, payload)
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API {method} failed: {json.dumps(data, ensure_ascii=False)}")
    return data

async def register_bot_commands(bot_token: str) -> None:
    commands = [
        {
            "command": "start",
            "description": "恢复菜单",
        }
    ]

    data = await telegram_raw(bot_token, "setMyCommands", {
        "commands": commands
    })

    if not data.get("ok"):
        logger.warning(
            "setMyCommands failed bot=%s resp=%s",
            mask_bot_token(bot_token),
            json.dumps(data, ensure_ascii=False),
        )

async def register_bot_commands_safe(bot_token: str) -> None:
    try:
        await register_bot_commands(bot_token)
    except Exception:
        logger.exception("register_bot_commands_safe failed")
