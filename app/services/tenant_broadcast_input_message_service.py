from app.telegram.api import tg
from app.utils.helpers import sanitize_tenant_id
from app.services.apply_service import clear_apply_session, save_apply_session
from app.services.bot_service import load_bot, list_started_users
from app.services.tenant_service import load_tenant, is_platform_tenant_blacklisted


async def try_handle_tenant_broadcast_input_message(
    *,
    platform_bot_token: str,
    chat_id: int,
    text: str,
    session: dict,
) -> bool:
    if not session or session.get("mode") != "tenant_broadcast":
        return False

    if session.get("step") != "broadcast_input":
        return False

    tenant_id = sanitize_tenant_id(session.get("tenantId") or "")
    bot_id = sanitize_tenant_id(session.get("botId") or "")
    broadcast_text = text.strip()

    if not tenant_id or not bot_id or not broadcast_text:
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "群发内容不能为空。",
        })
        return True

    tenant = await load_tenant(tenant_id)
    if not tenant:
        await clear_apply_session(chat_id)
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "租户不存在或已删除。",
        })
        return True

    if int(tenant.get("adminChatId", 0)) != int(chat_id):
        await clear_apply_session(chat_id)
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "你没有权限操作这个机器人。",
        })
        return True

    if await is_platform_tenant_blacklisted(tenant_id):
        await clear_apply_session(chat_id)
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "该租户已被平台拉黑，禁止群发。",
        })
        return True

    sender_bot = await load_bot(bot_id)
    if not sender_bot:
        await clear_apply_session(chat_id)
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "机器人不存在或已删除，无法群发。",
        })
        return True

    if str(sender_bot.get("tenantId") or "").strip() != tenant_id:
        await clear_apply_session(chat_id)
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "机器人不属于当前租户，无法群发。",
        })
        return True

    users = await list_started_users(bot_id)
    if not users:
        await clear_apply_session(chat_id)
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": f"发送机器人 @{session.get('botUsername') or bot_id} 暂无可群发用户。",
        })
        return True

    session["step"] = "broadcast_confirm"
    session["broadcastText"] = broadcast_text
    session["targetCount"] = len(users)
    session["senderBotId"] = bot_id
    session["senderBotUsername"] = str(((sender_bot.get("botInfo") or {}).get("username") or "")).strip()
    await save_apply_session(chat_id, session)

    sender_show = (
        f"@{session['senderBotUsername']}"
        if session["senderBotUsername"] else session["senderBotId"]
    )

    await tg(platform_bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": (
            f"📣 即将群发给机器人：{sender_show}\n"
            f"目标人数：{len(users)}\n\n"
            f"群发内容：\n{broadcast_text}\n\n"
            "请确认是否发送。"
        ),
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "✅ 确认", "callback_data": "tenant_broadcast_confirm"},
                {"text": "❌ 取消", "callback_data": "tenant_broadcast_cancel"},
            ]]
        },
    })
    return True
