async def finish_admin_tenant_broadcast_confirm(
    *,
    platform_bot_token: str,
    from_id: int,
    message: dict,
    tenant_id: str,
    tenant: dict,
    sender_bot: dict,
    users: list,
    success: int,
    failed: int,
) -> None:
    from app.telegram.api import tg
    from app.services.apply_service import clear_apply_session

    await clear_apply_session(from_id)

    if message.get("chat", {}).get("id") and message.get("message_id"):
        try:
            await tg(platform_bot_token, "editMessageReplyMarkup", {
                "chat_id": message["chat"]["id"],
                "message_id": message["message_id"],
                "reply_markup": {"inline_keyboard": []},
            })
        except Exception:
            pass

    sender_show = str(((sender_bot.get("botInfo") or {}).get("username") or "")).strip()
    sender_show = f"@{sender_show}" if sender_show else str(sender_bot.get("botId") or "")

    await tg(platform_bot_token, "sendMessage", {
        "chat_id": from_id,
        "text": (
            "📣 群发完成\n"
            f"租户：{tenant.get('tenantName') or tenant_id}\n"
            f"发送机器人：{sender_show}\n"
            f"目标人数：{len(users)}\n"
            f"成功：{success}\n"
            f"失败：{failed}"
        ),
    })
