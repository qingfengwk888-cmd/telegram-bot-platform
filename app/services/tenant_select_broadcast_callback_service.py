import re


async def try_handle_tenant_select_broadcast_callback(
    *,
    platform_bot_token: str,
    from_id: int,
    username: str,
    display_name: str,
    data: str,
    callback_id: str,
    session: dict | None,
    bot: dict | None,
    bot_id: str | None,
) -> bool:
    from app.telegram.api import tg
    from app.utils.helpers import sanitize_tenant_id
    from app.services.tenant_service import load_tenant
    from app.services.bot_service import pick_default_bot_for_tenant
    from app.services.apply_service import save_apply_session

    m = re.match(r"^tenant_select:broadcast:(.+)$", data)
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

    if not session:
        session = {
            "mode": "modify",
            "step": "",
            "applicantChatId": from_id,
            "applicantUsername": username,
            "applicantDisplayName": display_name,
            "tenantId": "",
            "tenantName": "",
            "botUsername": "",
            "fieldKey": "",
            "fieldLabel": "",
            "newValue": "",
            "buttonDrafts": [],
            "currentButtonText": "",
            "currentButtonReply": "",
        }

    if not bot:
        bot = await pick_default_bot_for_tenant(tenant_id)

    if not bot:
        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "该租户下暂无可操作机器人",
            "show_alert": True,
        })
        return True

    bot_id = str(bot_id or bot.get("botId") or "").strip()
    bot_username = str(((bot.get("botInfo") or {}).get("username") or "")).strip()

    session["mode"] = "tenant_broadcast"
    session["step"] = "broadcast_input"
    session["tenantId"] = bot.get("tenantId") or ""
    session["tenantName"] = bot.get("tenantName") or bot.get("tenantId") or ""
    session["botId"] = bot_id
    session["botUsername"] = bot_username

    await save_apply_session(from_id, session)

    await tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": "已选择机器人",
    })

    await tg(platform_bot_token, "sendMessage", {
        "chat_id": from_id,
        "text": f"你正在给 @{session['botUsername'] or bot_id} 的启动用户群发。\n\n请直接发送群发内容。",
    })
    return True
