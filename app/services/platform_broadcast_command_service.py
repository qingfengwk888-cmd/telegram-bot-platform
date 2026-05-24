from app.telegram.api import tg
from app.utils.helpers import sanitize_tenant_id
from app.services.tenant_service import (
    load_tenant,
    list_started_users_by_tenant_id,
    is_platform_tenant_blacklisted,
)


async def try_handle_platform_broadcast_command(
    *,
    platform_bot_token: str,
    chat_id: int,
    text: str,
) -> bool:
    if not text.startswith("/broadcast"):
        return False

    if text.startswith("/broadcast_all"):
        return False

    parts = text.split(maxsplit=2)
    if len(parts) < 3:
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "用法：/broadcast tenantId 群发内容",
        })
        return True

    tenant_id = sanitize_tenant_id(parts[1])
    broadcast_text = parts[2].strip()

    if not tenant_id or not broadcast_text:
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "参数不完整。用法：/broadcast tenantId 群发内容",
        })
        return True

    tenant = await load_tenant(tenant_id)
    if not tenant:
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "租户不存在。",
        })
        return True

    if await is_platform_tenant_blacklisted(tenant_id):
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "该租户已被拉黑，禁止操作。",
        })
        return True

    users = await list_started_users_by_tenant_id(tenant_id)
    if not users:
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "该租户暂无启动用户，无法群发。",
        })
        return True

    success = 0
    failed = 0

    for u in users:
        try:
            await tg(tenant["botToken"], "sendMessage", {
                "chat_id": int(u["userId"]),
                "text": broadcast_text,
            })
            success += 1
        except Exception:
            failed += 1

    await tg(platform_bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": (
            "📣 单租户群发完成\n"
            f"租户：{tenant_id}\n"
            f"目标人数：{len(users)}\n"
            f"成功：{success}\n"
            f"失败：{failed}"
        ),
    })
    return True
