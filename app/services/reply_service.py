from app.telegram.api import tg


async def reply_rate_limited_for_callback(bot_token: str, callback_id: str, message: str) -> None:
    if not message:
        return

    await tg(bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": message,
        "show_alert": True,
    })


async def reply_rate_limited_for_message(bot_token: str, chat_id: int, message: str) -> None:
    if not message:
        return

    await tg(bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": message,
    })
