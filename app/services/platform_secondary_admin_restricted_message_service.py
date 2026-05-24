from app.telegram.api import tg
from app.utils.helpers import is_secondary_platform_admin


async def try_handle_platform_secondary_admin_restricted_message(
    *,
    platform_bot_token: str,
    chat_id: int,
    text: str,
) -> bool:
    if not is_secondary_platform_admin(chat_id):
        return False

    if text not in {"🌐 全部群发", "📢 广告设置"}:
        return False

    await tg(platform_bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": "❌ 你没有权限使用该功能。",
    })
    return True
