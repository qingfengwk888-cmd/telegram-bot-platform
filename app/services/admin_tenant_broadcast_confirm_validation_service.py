async def validate_admin_tenant_broadcast_confirm_session(
    *,
    platform_bot_token: str,
    callback_query: dict,
    from_id: int,
    session: dict | None,
):
    from app import legacy_app as legacy

    if not session or session.get("mode") != "admin_tenant_broadcast" or session.get("step") != "broadcast_confirm":
        await legacy.tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "群发会话已失效，请重新操作",
            "show_alert": True,
        })
        return False, "", "", None, None, []

    tenant_id = legacy.sanitize_tenant_id(session.get("tenantId") or "")
    broadcast_text = str(session.get("broadcastText") or "").strip()
    sender_bot_id = legacy.sanitize_tenant_id(session.get("senderBotId") or "")

    if not tenant_id or not broadcast_text or not sender_bot_id:
        await legacy.clear_apply_session(from_id)
        await legacy.tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "群发内容无效，请重新操作",
            "show_alert": True,
        })
        return False, "", "", None, None, []

    tenant = await legacy.load_tenant(tenant_id)
    if not tenant:
        await legacy.clear_apply_session(from_id)
        await legacy.tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "租户不存在或已删除",
            "show_alert": True,
        })
        return False, "", "", None, None, []

    if await legacy.is_platform_tenant_blacklisted(tenant_id):
        await legacy.clear_apply_session(from_id)
        await legacy.tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "该租户已被拉黑，禁止群发",
            "show_alert": True,
        })
        return False, "", "", None, None, []

    sender_bot = await legacy.load_bot(sender_bot_id)
    if not sender_bot or str(sender_bot.get("status") or "active") != "active":
        await legacy.clear_apply_session(from_id)
        await legacy.tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "发送机器人不存在或不可用",
            "show_alert": True,
        })
        return False, "", "", None, None, []

    if str(sender_bot.get("tenantId") or "") != tenant_id:
        await legacy.clear_apply_session(from_id)
        await legacy.tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "发送机器人与租户不匹配",
            "show_alert": True,
        })
        return False, "", "", None, None, []

    users = await legacy.list_started_users_by_tenant_id(tenant_id)
    if not users:
        await legacy.clear_apply_session(from_id)
        await legacy.tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "该租户暂无启动用户",
            "show_alert": True,
        })
        return False, "", "", None, None, []

    return True, tenant_id, broadcast_text, tenant, sender_bot, users
