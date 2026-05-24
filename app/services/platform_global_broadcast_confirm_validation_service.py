async def validate_platform_global_broadcast_confirm_session(
    *,
    platform_bot_token: str,
    callback_query: dict,
    from_id: int,
    session: dict | None,
) -> tuple[bool, str, str]:
    from app.telegram.api import tg
    from app.services.apply_service import clear_apply_session

    if not session or session.get("mode") != "platform_global_broadcast" or session.get("step") != "broadcast_confirm":
        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "全部群发会话已失效，请重新操作",
            "show_alert": True,
        })
        return False, "", ""

    broadcast_text = str(session.get("broadcastText") or "").strip()
    target_type = str(session.get("targetType") or "").strip()

    if not broadcast_text or target_type not in {"tenants", "tenant_users", "all_people"}:
        await clear_apply_session(from_id)
        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "群发内容或范围无效，请重新操作",
            "show_alert": True,
        })
        return False, "", ""

    return True, broadcast_text, target_type
