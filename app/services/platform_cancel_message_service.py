from app.telegram.api import tg
from app.services.apply_service import clear_apply_session


async def try_handle_platform_cancel_message(
    *,
    platform_bot_token: str,
    chat_id: int,
    text: str,
) -> bool:
    if not text.startswith("/cancel"):
        return False

    await clear_apply_session(chat_id)
    await tg(platform_bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": "✅ 已取消当前流程。",
    })
    return True
