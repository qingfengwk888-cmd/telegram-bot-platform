from app.services.rate_limit_service import get_bot_user_rate_limit_status
from app.services.bot_admin_user_action_callback_service import try_handle_bot_admin_user_action_callback
from app.telegram.api import tg


async def handle_bot_webhook_callback_query(
    *,
    bot_id: str,
    bot: dict,
    callback_query: dict,
) -> dict:
    from_user = callback_query.get("from") or {}
    from_id = int(from_user.get("id") or 0)
    callback_id = callback_query.get("id")
    data = str(callback_query.get("data") or "").strip()

    limit_result = await get_bot_user_rate_limit_status(
        bot_id=bot_id,
        user_id=from_id,
        action=f"callback:{data}",
    )

    if limit_result["blocked"]:
        if limit_result["message"]:
            await tg(bot["botToken"], "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": limit_result["message"],
                "show_alert": True,
            })
        return {"ok": True, "botId": bot_id, "role": "bot_callback_rate_limited"}

    if await try_handle_bot_admin_user_action_callback(
        bot_id=bot_id,
        bot=bot,
        callback_query=callback_query,
    ):
        return {"ok": True, "botId": bot_id, "role": "bot_admin_user_action"}

    await tg(bot["botToken"], "answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": "已处理",
    })
    return {"ok": True, "botId": bot_id, "role": "bot_callback"}
