import re
import time
from typing import List


async def try_handle_tenant_select_blacklist_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
    callback_id: str,
) -> bool:
    from app import legacy_app as legacy

    m = re.match(r"^tenant_select:blacklist:(.+)$", data)
    if not m:
        return False

    tenant_id = legacy.sanitize_tenant_id(m.group(1))

    tenant = await legacy.load_tenant(tenant_id)
    if not tenant:
        await legacy.tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "机器人不存在",
            "show_alert": True,
        })
        return True

    if int(tenant.get("adminChatId", 0)) != int(from_id):
        await legacy.tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "你没有权限操作这个机器人",
            "show_alert": True,
        })
        return True

    started = time.perf_counter()

    await legacy.tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": "处理中...",
    })

    bots = await legacy.list_bots_by_tenant_id(tenant_id)
    all_users: List[dict] = []

    for bot in bots:
        bot_id = str(bot.get("botId") or "").strip()
        if not bot_id:
            continue

        users = await legacy.list_blacklisted_users(bot_id)
        bot_username = str(((bot.get("botInfo") or {}).get("username") or "")).strip()

        for u in users:
            all_users.append({
                **u,
                "botId": bot_id,
                "botUsername": bot_username,
                "tenantId": tenant_id,
            })

    all_users.sort(key=lambda x: int(x.get("userId") or 0))

    await legacy.tg(platform_bot_token, "sendMessage", {
        "chat_id": from_id,
        "text": legacy.format_tenant_blacklisted_users_text(tenant, all_users),
        "parse_mode": "HTML",
    })

    legacy.logger.info(
        "perf tenant_select:blacklist tenant_id=%s bots=%s users=%s cost_ms=%s",
        tenant_id,
        len(bots),
        len(all_users),
        legacy.cost_ms(started),
    )
    return True
