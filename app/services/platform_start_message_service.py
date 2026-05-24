from app.telegram.api import tg
from app.services.apply_service import clear_apply_session
from app.telegram.keyboards import (
    build_platform_reply_keyboard_for_admin,
    build_platform_reply_keyboard_for_tenant,
)


async def try_handle_platform_start_message(
    *,
    platform_bot_token: str,
    chat_id: int,
    text: str,
    is_platform_admin: bool,
) -> bool:
    if not text.startswith("/start"):
        return False

    await clear_apply_session(chat_id)
    await tg(platform_bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": (
            "👋 欢迎使用双向机器人\n\n"
            + (
                "你当前进入的是【平台管理员后台】"
                if is_platform_admin
                else "点击“添加机器人”开始"
            )
        ),
        "reply_markup": (
            build_platform_reply_keyboard_for_admin(chat_id)
            if is_platform_admin
            else build_platform_reply_keyboard_for_tenant()
        ),
    })
    return True
