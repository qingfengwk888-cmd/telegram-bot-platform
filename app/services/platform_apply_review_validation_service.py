async def load_and_validate_platform_apply_review(
    *,
    callback_query: dict,
    platform_bot_token: str,
    apply_id: str,
):
    from app.telegram.api import tg
    from app.services.apply_service import load_apply

    apply = await load_apply(apply_id)

    if not apply:
        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "申请不存在或已过期",
            "show_alert": True,
        })
        return False, None

    if apply.get("status") != "pending":
        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": f"该申请已处理：{apply.get('status')}",
            "show_alert": True,
        })
        return False, None

    return True, apply
