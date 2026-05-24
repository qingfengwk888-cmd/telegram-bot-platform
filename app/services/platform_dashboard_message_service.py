from app.telegram.api import tg
from app.services.platform_dashboard_view_service import build_platform_dashboard_text


async def try_handle_platform_dashboard_message(
    *,
    platform_bot_token: str,
    chat_id: int,
    text: str,
) -> bool:
    if text != "📊 数据概览":
        return False

    dashboard_text = await build_platform_dashboard_text()

    await tg(platform_bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": dashboard_text,
        "parse_mode": "HTML",
    })
    return True
