import re


async def try_handle_bot_blacklist_detail_back_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    data: str,
    callback_id: str,
) -> bool:
    from app.telegram.api import tg
    from app.utils.helpers import sanitize_tenant_id
    from app.services.bot_service import load_bot
    from app.telegram.keyboards import build_single_bot_action_buttons

    m_blacklist_back = re.match(r"^bot_blacklist_back:(.+)$", data)
    if not m_blacklist_back:
        return False

    bot_id = sanitize_tenant_id(m_blacklist_back.group(1))
    bot = await load_bot(bot_id)

    if not bot:
        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "机器人不存在",
            "show_alert": True,
        })
        return True

    bot_username = str(((bot.get("botInfo") or {}).get("username") or "")).strip()
    show_name = f"@{bot_username}" if bot_username else (bot.get("tenantName") or bot_id)

    await tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": "返回上一级",
    })
    await tg(platform_bot_token, "editMessageText", {
        "chat_id": callback_query["message"]["chat"]["id"],
        "message_id": callback_query["message"]["message_id"],
        "text": f"当前机器人：{show_name}",
        "reply_markup": build_single_bot_action_buttons(bot_id),
    })
    return True
