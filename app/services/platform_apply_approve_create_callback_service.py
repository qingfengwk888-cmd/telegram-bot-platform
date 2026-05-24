async def handle_platform_apply_approve_create_callback(
    *,
    request,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    apply: dict,
    message: dict,
) -> None:
    from app.telegram.api import tg
    from app.utils.helpers import now_ms, escape_html
    from app.services.apply_service import create_bot_from_apply, save_apply
    from app.telegram.formatters import build_apply_summary

    result = await create_bot_from_apply(request, apply)

    apply["status"] = "approved"
    apply["reviewedAt"] = now_ms()
    apply["reviewerChatId"] = from_id
    apply["reviewerAction"] = "approve"
    apply["approvedTenantId"] = result["tenant"]["tenantId"]
    await save_apply(apply)

    await tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_query["id"],
        "text": "已同意并创建成功",
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
            "text": (
                f"{build_apply_summary(apply)}\n\n"
                "✅ <b>已通过</b>\n"
                f"🏢 tenantId：<code>{escape_html(result['tenant']['tenantId'])}</code>"
            ),
            "parse_mode": "HTML",
        })

    await tg(platform_bot_token, "sendMessage", {
        "chat_id": apply["applicantChatId"],
        "text": (
            "✅ 你的机器人接入申请已通过审核。\n\n"
            "机器人已完成接入，可以开始使用。\n"
            "如需修改配置，请按现有流程进入对应机器人管理。"
        ),
    })

    await tg(apply["botToken"], "sendMessage", {
        "chat_id": apply["applicantChatId"],
        "text": "✅ 接入成功",
    })
