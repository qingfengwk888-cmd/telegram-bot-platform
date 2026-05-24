from app.telegram.api import tg
from app.services.tenant_service import (
    get_tenant_index,
    load_tenant,
    list_started_users_by_tenant_id,
    is_platform_tenant_blacklisted,
)


async def try_handle_platform_broadcast_all_command(
    *,
    platform_bot_token: str,
    chat_id: int,
    text: str,
) -> bool:
    if not text.startswith("/broadcast_all"):
        return False

    parts = text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "用法：/broadcast_all 群发内容",
        })
        return True

    broadcast_text = parts[1].strip()
    tenant_ids = await get_tenant_index()

    total_target = 0
    success = 0
    failed = 0

    for tenant_id in tenant_ids:
        tenant = await load_tenant(tenant_id)
        if not tenant:
            continue

        if await is_platform_tenant_blacklisted(tenant_id):
            continue

        users = await list_started_users_by_tenant_id(tenant_id)
        for u in users:
            user_id = int(u["userId"])
            total_target += 1

            try:
                await tg(tenant["botToken"], "sendMessage", {
                    "chat_id": user_id,
                    "text": broadcast_text,
                })
                success += 1
            except Exception:
                failed += 1

    await tg(platform_bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": (
            "🌐 全部群发完成\n"
            f"目标人数：{total_target}\n"
            f"成功：{success}\n"
            f"失败：{failed}"
        ),
    })
    return True
