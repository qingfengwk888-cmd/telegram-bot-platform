import logging
import re
import time
from typing import List


logger = logging.getLogger(__name__)


async def try_handle_tenant_select_blacklist_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
    callback_id: str,
) -> bool:
    from app.telegram.api import tg
    from app.utils.helpers import sanitize_tenant_id, cost_ms
    from app.services.tenant_service import load_tenant, list_bots_by_tenant_id
    from app.services.blacklist_service import list_blacklisted_users, format_tenant_blacklisted_users_text

    m = re.match(r"^tenant_select:blacklist:(.+)$", data)
    if not m:
        return False

    tenant_id = sanitize_tenant_id(m.group(1))

    tenant = await load_tenant(tenant_id)
    if not tenant:
        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "机器人不存在",
            "show_alert": True,
        })
        return True

    if int(tenant.get("adminChatId", 0)) != int(from_id):
        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "你没有权限操作这个机器人",
            "show_alert": True,
        })
        return True

    started = time.perf_counter()

    await tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": "处理中...",
    })

    bots = await list_bots_by_tenant_id(tenant_id)
    all_users: List[dict] = []

    for bot in bots:
        bot_id = str(bot.get("botId") or "").strip()
        if not bot_id:
            continue

        users = await list_blacklisted_users(bot_id)
        bot_username = str(((bot.get("botInfo") or {}).get("username") or "")).strip()

        for u in users:
            all_users.append({
                **u,
                "botId": bot_id,
                "botUsername": bot_username,
                "tenantId": tenant_id,
            })

    all_users.sort(key=lambda x: int(x.get("userId") or 0))

    await tg(platform_bot_token, "sendMessage", {
        "chat_id": from_id,
        "text": format_tenant_blacklisted_users_text(tenant, all_users),
        "parse_mode": "HTML",
    })

    logger.info(
        "perf tenant_select:blacklist tenant_id=%s bots=%s users=%s cost_ms=%s",
        tenant_id,
        len(bots),
        len(all_users),
        cost_ms(started),
    )
    return True
