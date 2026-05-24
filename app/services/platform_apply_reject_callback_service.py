async def try_handle_platform_apply_reject_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    action: str,
    apply: dict,
    message: dict,
) -> bool:
    from app import legacy_app as legacy

    if action != "reject":
        return False

    apply["status"] = "rejected"
    apply["reviewedAt"] = legacy.now_ms()
    apply["reviewerChatId"] = from_id
    apply["reviewerAction"] = "reject"
    apply["rejectReason"] = "管理员拒绝"

    await legacy.save_apply(apply)

    await legacy.tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_query["id"],
        "text": "已拒绝",
    })

    if message.get("chat", {}).get("id") and message.get("message_id"):
        await legacy.tg(platform_bot_token, "editMessageReplyMarkup", {
            "chat_id": message["chat"]["id"],
            "message_id": message["message_id"],
            "reply_markup": {"inline_keyboard": []},
        })
        await legacy.tg(platform_bot_token, "editMessageText", {
            "chat_id": message["chat"]["id"],
            "message_id": message["message_id"],
            "text": f"{legacy.build_apply_summary(apply)}\n\n❌ <b>已拒绝</b>",
            "parse_mode": "HTML",
        })

    await legacy.tg(platform_bot_token, "sendMessage", {
        "chat_id": apply["applicantChatId"],
        "text": (
            "❌ 很抱歉，你的修改申请未通过审核。"
            if apply.get("type") == "update"
            else "❌ 很抱歉，你的机器人接入申请未通过审核。"
        ),
    })
    return True
