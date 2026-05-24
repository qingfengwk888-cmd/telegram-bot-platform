from app.telegram.api import tg
from app.utils.helpers import sanitize_tenant_id
from app.services.blacklist_service import list_blacklisted_users, format_blacklisted_users_text
from app.services.tenant_service import load_tenant_by_admin_chat_id, list_bots_by_tenant_id
from app.telegram.keyboards import build_bot_pick_buttons


async def try_handle_tenant_blacklist_view_message(
    *,
    platform_bot_token: str,
    chat_id: int,
    text: str,
) -> bool:
    if text != "🚫 查看黑名单":
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

    if len(bots) == 1:
        bot = bots[0]
        bot_id = sanitize_tenant_id(bot.get("botId") or "")
        users = await list_blacklisted_users(bot_id)

        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": format_blacklisted_users_text(bot, users),
            "parse_mode": "HTML",
        })
        return True

    await tg(platform_bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": "请选择一个机器人查看黑名单：",
        "reply_markup": build_bot_pick_buttons(bots, "blacklist"),
    })
    return True
