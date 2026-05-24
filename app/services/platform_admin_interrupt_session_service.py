from app.services.apply_service import clear_apply_session
from app.services.input_session_service import is_busy_input_session


ADMIN_INTERRUPT_TEXT_ACTIONS = {
    "📊 数据概览",
    "🏢 所有租户",
    "🌐 全部群发",
    "📢 广告设置",
    "/start",
    "/cancel",
}


async def interrupt_platform_admin_input_session_if_needed(
    *,
    chat_id: int,
    text: str,
    is_platform_admin: bool,
    session,
):
    if (
        is_platform_admin
        and text in ADMIN_INTERRUPT_TEXT_ACTIONS
        and is_busy_input_session(session)
    ):
        await clear_apply_session(chat_id)
        return None

    return session
