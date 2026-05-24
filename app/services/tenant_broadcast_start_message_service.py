from app.telegram.api import tg
from app.utils.helpers import sanitize_tenant_id
from app.services.apply_service import save_apply_session
from app.services.tenant_query_service import list_tenants_by_admin_chat_id
from app.telegram.keyboards import build_bot_pick_buttons


async def try_handle_tenant_broadcast_start_message(
    *,
    platform_bot_token: str,
    chat_id: int,
    text: str,
) -> bool:
    if text != "📣 群发消息":
        return False

    tenants = await list_tenants_by_admin_chat_id(chat_id)
    if not tenants:
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "你暂未接入机器人。",
        })
        return True

    if len(tenants) == 1:
        tenant = tenants[0]
        tenant_id = sanitize_tenant_id(tenant.get("tenantId") or "")

        await save_apply_session(chat_id, {
            "mode": "tenant_broadcast",
            "step": "broadcast_input",
            "tenantId": tenant_id,
            "tenantName": tenant.get("tenantName") or tenant_id,
            "botUsername": str(((tenant.get("botInfo") or {}).get("username") or "")).strip(),
        })

        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "你正在给 所有启动用户 群发。\n\n请直接发送群发内容。",
        })
        return True

    await tg(platform_bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": "Please select robot：",
        "reply_markup": build_bot_pick_buttons(tenants, "broadcast"),
    })
    return True
