from app.telegram.api import tg
from app.utils.helpers import sanitize_tenant_id
from app.services.tenant_service import load_tenant, list_started_users_by_tenant_id
from app.telegram.formatters import (
    format_tenant_summary_text,
    format_started_users_text,
    format_tenant_category_text,
)


async def try_handle_platform_users_command(
    *,
    platform_bot_token: str,
    chat_id: int,
    text: str,
) -> bool:
    if not text.startswith("/users"):
        return False

    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "用法：/users tenantId",
        })
        return True

    tenant_id = sanitize_tenant_id(parts[1])
    if not tenant_id:
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "tenantId 无效。",
        })
        return True

    tenant = await load_tenant(tenant_id)
    if not tenant:
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "租户不存在",
        })
        return True

    users = await list_started_users_by_tenant_id(tenant_id)

    await tg(platform_bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": (
            (await format_tenant_summary_text(tenant))
            + "\n\n"
            + format_started_users_text(tenant, users)
            + "\n\n"
            + format_tenant_category_text(tenant)
        ),
        "parse_mode": "HTML",
    })
    return True
