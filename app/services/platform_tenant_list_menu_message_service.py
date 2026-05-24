from app.telegram.api import tg
from app.telegram.keyboards import build_admin_tenant_root_menu_buttons


async def try_handle_platform_tenant_list_menu_message(
    *,
    platform_bot_token: str,
    chat_id: int,
    text: str,
) -> bool:
    if text != "🏢 所有租户":
        return False

    await tg(platform_bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": "🏢 所有租户\n\n请选择查看方式：",
        "reply_markup": build_admin_tenant_root_menu_buttons(),
    })
    return True
