import re


async def try_handle_tenant_select_buttons_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
    callback_id: str,
) -> bool:
    from app import legacy_app as legacy

    m = re.match(r"^tenant_select:buttons:(.+)$", data)
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

    await legacy.clear_apply_session(from_id)

    bot = await legacy.pick_default_bot_for_tenant(tenant_id)
    if not bot:
        await legacy.tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "该租户下暂无可操作机器人",
            "show_alert": True,
        })
        return True

    bot_id = str(bot.get("botId") or "").strip()
    bot_username = str(((bot.get("botInfo") or {}).get("username") or "")).strip()
    show_name = f"@{bot_username}" if bot_username else (bot.get("tenantName") or bot_id)

    await legacy.tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": "请选择按钮操作",
    })
    await legacy.tg(platform_bot_token, "editMessageText", {
        "chat_id": callback_query["message"]["chat"]["id"],
        "message_id": callback_query["message"]["message_id"],
        "text": f"当前机器人：{show_name}",
        "reply_markup": legacy.build_button_manage_menu_buttons(bot_id),
    })
    return True
