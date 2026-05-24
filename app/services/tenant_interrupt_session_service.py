from app.services.input_session_service import interrupt_input_session_if_needed


TENANT_INTERRUPT_TEXT_ACTIONS = {
    "📝 添加机器人",
    "📁 我的机器人",
    "🚫 查看黑名单",
    "📣 群发消息",
    "💬 帮助中心",
    "🇨🇳 切换中文包",
    "/apply",
    "/my",
    "/start",
    "/cancel",
}


async def interrupt_tenant_input_session_if_needed(
    *,
    chat_id: int,
    text: str,
    session,
    platform_bot_token: str,
):
    if text in TENANT_INTERRUPT_TEXT_ACTIONS:
        return await interrupt_input_session_if_needed(
            chat_id,
            session,
            platform_bot_token=platform_bot_token,
            notify_chat_id=chat_id,
        )

    return session
