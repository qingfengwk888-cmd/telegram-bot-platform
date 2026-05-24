from app.telegram.api import tg
from app.utils.helpers import sanitize_tenant_id
from app.services.apply_service import clear_apply_session
from app.services.tenant_service import (
    load_tenant,
    list_started_users_by_tenant_id,
    is_platform_tenant_blacklisted,
)


async def try_handle_platform_admin_tenant_broadcast_legacy_input(
    *,
    platform_bot_token: str,
    chat_id: int,
    text: str,
    session: dict,
) -> bool:
    if not session or session.get("mode") != "admin_tenant_broadcast":
        return False

    if session.get("step") != "broadcast_input":
        return False

    tenant_id = sanitize_tenant_id(session.get("tenantId") or "")
    broadcast_text = text.strip()

    if not tenant_id or not broadcast_text:
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "群发内容不能为空。",
        })
        return True

    tenant = await load_tenant(tenant_id)
    if not tenant:
        await clear_apply_session(chat_id)
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "租户不存在或已删除。",
        })
        return True

    if await is_platform_tenant_blacklisted(tenant_id):
        await clear_apply_session(chat_id)
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "该租户已被拉黑，禁止群发。",
        })
        return True

    users = await list_started_users_by_tenant_id(tenant_id)
    if not users:
        await clear_apply_session(chat_id)
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "该租户暂无启动用户，无法群发。",
        })
        return True

    success = 0
    failed = 0

    for u in users:
        user_id = int(u["userId"])
        try:
            await tg(tenant["botToken"], "sendMessage", {
                "chat_id": user_id,
                "text": broadcast_text,
            })
            success += 1
        except Exception:
            failed += 1

    await clear_apply_session(chat_id)

    await tg(platform_bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": (
            "📣 群发完成\n"
            f"租户：{tenant_id}\n"
            f"目标人数：{len(users)}\n"
            f"成功：{success}\n"
            f"失败：{failed}"
        ),
    })
    return True
