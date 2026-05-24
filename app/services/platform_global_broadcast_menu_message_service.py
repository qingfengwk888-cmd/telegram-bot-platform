from app.telegram.api import tg
from app.telegram.keyboards import build_global_broadcast_target_buttons
from app.services.apply_service import clear_apply_session


async def try_handle_platform_global_broadcast_menu_message(
    *,
    platform_bot_token: str,
    chat_id: int,
    text: str,
) -> bool:
    if text != "🌐 全部群发":
        return False

    await clear_apply_session(chat_id)

    await tg(platform_bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": "请选择群发范围：",
        "reply_markup": build_global_broadcast_target_buttons(),
    })
    return True
