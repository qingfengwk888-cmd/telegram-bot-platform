from app.telegram.api import tg
from app.services.apply_service import save_apply_session


async def try_handle_tenant_apply_start_message(
    *,
    platform_bot_token: str,
    chat_id: int,
    text: str,
    username: str,
    display_name: str,
    name_text: str,
) -> bool:
    if text != "📝 添加机器人" and not text.startswith("/apply"):
        return False

    await save_apply_session(chat_id, {
        "mode": "create",
        "step": "bot_token",
        "applicantChatId": chat_id,
        "applicantUsername": username,
        "applicantDisplayName": display_name,
        "tenantName": username or name_text or f"user_{chat_id}",
        "tenantId": "",
        "botToken": "",
    })

    await tg(platform_bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": "📝 开始添加\n\n请直接发送机器人 Bot Token。",
    })
    return True
