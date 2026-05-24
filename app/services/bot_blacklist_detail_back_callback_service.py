import re


async def try_handle_bot_blacklist_detail_back_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    data: str,
    callback_id: str,
) -> bool:
    from app import legacy_app as legacy

    m_blacklist_back = re.match(r"^bot_blacklist_back:(.+)$", data)
    if not m_blacklist_back:
        return False

    bot_id = legacy.sanitize_tenant_id(m_blacklist_back.group(1))
    bot = await legacy.load_bot(bot_id)

    if not bot:
        await legacy.tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "机器人不存在",
            "show_alert": True,
        })
        return True

    bot_username = str(((bot.get("botInfo") or {}).get("username") or "")).strip()
    show_name = f"@{bot_username}" if bot_username else (bot.get("tenantName") or bot_id)

    await legacy.tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": "返回上一级",
    })
    await legacy.tg(platform_bot_token, "editMessageText", {
        "chat_id": callback_query["message"]["chat"]["id"],
        "message_id": callback_query["message"]["message_id"],
        "text": f"当前机器人：{show_name}",
        "reply_markup": legacy.build_single_bot_action_buttons(bot_id),
    })
    return True
