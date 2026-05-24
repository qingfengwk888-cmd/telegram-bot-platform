import re


async def try_handle_tenant_remove_confirm_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
    callback_id: str,
) -> bool:
    from app import legacy_app as legacy

    m_remove = re.match(r"^tenant_remove:(.+)$", data)
    if not m_remove:
        return False

    tenant_id = legacy.sanitize_tenant_id(m_remove.group(1))
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

    bot_username = str(((tenant.get("botInfo") or {}).get("username") or "")).strip()
    show_name = f"@{bot_username}" if bot_username else (tenant.get("tenantName") or tenant_id)

    await legacy.tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": "请确认",
    })

    await legacy.tg(platform_bot_token, "editMessageText", {
        "chat_id": callback_query["message"]["chat"]["id"],
        "message_id": callback_query["message"]["message_id"],
        "text": f"确认移除机器人 {show_name} 吗？",
        "reply_markup": legacy.build_remove_confirm_buttons(tenant_id),
    })
    return True
