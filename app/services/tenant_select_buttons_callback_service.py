import re


async def try_handle_tenant_select_buttons_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
    callback_id: str,
) -> bool:
    from app.telegram.api import tg
    from app.utils.helpers import sanitize_tenant_id
    from app.services.tenant_service import load_tenant
    from app.services.apply_service import clear_apply_session
    from app.services.bot_service import pick_default_bot_for_tenant
    from app.telegram.keyboards import build_button_manage_menu_buttons

    m = re.match(r"^tenant_select:buttons:(.+)$", data)
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

    await clear_apply_session(from_id)

    bot = await pick_default_bot_for_tenant(tenant_id)
    if not bot:
        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "该租户下暂无可操作机器人",
            "show_alert": True,
        })
        return True

    bot_id = str(bot.get("botId") or "").strip()
    bot_username = str(((bot.get("botInfo") or {}).get("username") or "")).strip()
    show_name = f"@{bot_username}" if bot_username else (bot.get("tenantName") or bot_id)

    await tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": "请选择按钮操作",
    })
    await tg(platform_bot_token, "editMessageText", {
        "chat_id": callback_query["message"]["chat"]["id"],
        "message_id": callback_query["message"]["message_id"],
        "text": f"当前机器人：{show_name}",
        "reply_markup": build_button_manage_menu_buttons(bot_id),
    })
    return True
