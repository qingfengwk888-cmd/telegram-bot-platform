async def try_handle_platform_apply_approve_update_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    action: str,
    apply: dict,
    message: dict,
) -> bool:
    from app.telegram.api import tg
    from app.utils.helpers import now_ms
    from app.services.apply_service import apply_bot_update, save_apply
    from app.telegram.formatters import build_apply_summary

    if action != "approve" or apply.get("type") != "update":
        return False

    await apply_bot_update(apply)
    apply["status"] = "approved"
    apply["reviewedAt"] = now_ms()
    apply["reviewerChatId"] = from_id
    apply["reviewerAction"] = "approve"
    await save_apply(apply)

    await tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_query["id"],
        "text": "已同意修改",
    })

    if message.get("chat", {}).get("id") and message.get("message_id"):
        await tg(platform_bot_token, "editMessageReplyMarkup", {
            "chat_id": message["chat"]["id"],
            "message_id": message["message_id"],
            "reply_markup": {"inline_keyboard": []},
        })
        await tg(platform_bot_token, "editMessageText", {
            "chat_id": message["chat"]["id"],
            "message_id": message["message_id"],
            "text": f"{build_apply_summary(apply)}\n\n✅ <b>修改已通过</b>",
            "parse_mode": "HTML",
        })

    await tg(platform_bot_token, "sendMessage", {
        "chat_id": apply["applicantChatId"],
        "text": "✅ 你的修改申请已通过审核。\n新的配置已生效。",
    })
    return True
