from app.telegram.api import tg
from app.utils.helpers import sanitize_tenant_id, build_tenant_id_from_admin_chat_id
from app.services.message_classify_service import classify_platform_action
from app.services.rate_limit_service import get_bot_user_rate_limit_status
from app.services.tenant_service import (
    load_tenant_by_admin_chat_id,
    is_platform_tenant_blacklisted,
)


async def check_platform_tenant_message_guard(
    *,
    platform_bot_token: str,
    chat_id: int,
    text: str,
    is_platform_admin: bool,
):
    current_tenant = await load_tenant_by_admin_chat_id(chat_id)

    if not is_platform_admin and current_tenant:
        tenant_id = sanitize_tenant_id(current_tenant.get("tenantId") or "")
        action_name = classify_platform_action(text)

        if action_name != "platform_plain_text":
            tenant_id = build_tenant_id_from_admin_chat_id(chat_id)

            limit_result = await get_bot_user_rate_limit_status(
                bot_id=tenant_id,
                user_id=chat_id,
                action=action_name,
            )
            if limit_result["blocked"]:
                if limit_result["message"]:
                    await tg(platform_bot_token, "sendMessage", {
                        "chat_id": chat_id,
                        "text": limit_result["message"],
                    })
                return True, current_tenant

    if current_tenant:
        tenant_id = sanitize_tenant_id(current_tenant.get("tenantId") or "")
        if tenant_id and await is_platform_tenant_blacklisted(tenant_id):
            # 被拉黑租户，平台机器人直接忽略
            return True, current_tenant

    return False, current_tenant
