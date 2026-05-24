async def try_handle_platform_apply_reject_callback(
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
    from app.services.apply_service import save_apply
    from app.telegram.formatters import build_apply_summary

    if action != "reject":
        return False

    apply["status"] = "rejected"
    apply["reviewedAt"] = now_ms()
    apply["reviewerChatId"] = from_id
    apply["reviewerAction"] = "reject"
    apply["rejectReason"] = "管理员拒绝"

    await save_apply(apply)

    await tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_query["id"],
        "text": "已拒绝",
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
            "text": f"{build_apply_summary(apply)}\n\n❌ <b>已拒绝</b>",
            "parse_mode": "HTML",
        })

    await tg(platform_bot_token, "sendMessage", {
        "chat_id": apply["applicantChatId"],
        "text": (
            "❌ 很抱歉，你的修改申请未通过审核。"
            if apply.get("type") == "update"
            else "❌ 很抱歉，你的机器人接入申请未通过审核。"
        ),
    })
    return True
