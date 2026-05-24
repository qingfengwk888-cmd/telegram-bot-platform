from app.utils.helpers import is_primary_platform_admin, is_secondary_platform_admin
from app.services.tenant_interrupt_session_service import interrupt_tenant_input_session_if_needed
from app.services.platform_tenant_message_dispatch_service import dispatch_platform_tenant_message
from app.services.platform_admin_message_dispatch_service import dispatch_platform_admin_message
from app.services.platform_message_entry_dispatch_service import dispatch_platform_message_entry


async def dispatch_platform_message(
    *,
    request,
    platform_bot_token: str,
    chat_id: int,
    text: str,
    username: str,
    name_text: str,
    display_name: str,
) -> bool:
    is_platform_admin = (
        is_primary_platform_admin(chat_id)
        or is_secondary_platform_admin(chat_id)
    )

    handled, session = await dispatch_platform_message_entry(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        is_platform_admin=is_platform_admin,
    )
    if handled:
        return True

    # =========================================================
    # 管理员功能区
    # =========================================================
    if is_platform_admin and await dispatch_platform_admin_message(
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        session=session,
    ):
        return True

    # =========================================================
    # 租户功能区
    # =========================================================
    session = await interrupt_tenant_input_session_if_needed(
        chat_id=chat_id,
        text=text,
        session=session,
        platform_bot_token=platform_bot_token,
    )

    if await dispatch_platform_tenant_message(
        request=request,
        platform_bot_token=platform_bot_token,
        chat_id=chat_id,
        text=text,
        username=username,
        name_text=name_text,
        display_name=display_name,
        session=session,
    ):
        return True

    return False
