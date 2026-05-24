from app.telegram.api import tg


async def try_handle_tenant_modify_deprecated_message(
    *,
    platform_bot_token: str,
    chat_id: int,
    text: str,
) -> bool:
    if not text.startswith("/modify"):
        return False

    await tg(platform_bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": "当前已不在底部菜单展示该功能，请按你的现有流程使用。",
    })
    return True
