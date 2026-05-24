from app.telegram.api import tg
from app.services.tenant_service import load_tenant_by_admin_chat_id, list_bots_by_tenant_id
from app.telegram.keyboards import build_my_bots_entry_buttons


async def try_handle_tenant_my_bots_message(
    *,
    platform_bot_token: str,
    chat_id: int,
    text: str,
) -> bool:
    if text != "📁 我的机器人" and not text.startswith("/my"):
        return False

    tenant = await load_tenant_by_admin_chat_id(chat_id)
    if not tenant:
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "你暂未接入机器人。",
        })
        return True

    bots = await list_bots_by_tenant_id(tenant["tenantId"])
    if not bots:
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "你名下暂无机器人。",
        })
        return True

    await tg(platform_bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": "Choose a bot from the list below:",
        "reply_markup": build_my_bots_entry_buttons(bots),
    })
    return True
