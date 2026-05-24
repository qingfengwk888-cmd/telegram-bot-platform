from app.telegram.api import tg


async def try_handle_tenant_language_pack_message(
    *,
    platform_bot_token: str,
    chat_id: int,
    text: str,
) -> bool:
    if text != "🇨🇳 切换中文包":
        return False

    await tg(platform_bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": "点击下方按钮切换 Telegram 中文语言包：",
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "点击切换中文包", "url": "https://t.me/setlanguage/zhcncc"}
            ]]
        },
    })
    return True
