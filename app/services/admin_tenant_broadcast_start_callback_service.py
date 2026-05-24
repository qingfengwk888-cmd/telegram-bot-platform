import re


async def try_handle_admin_tenant_broadcast_start_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
) -> bool:
    from app import legacy_app as legacy

    broadcast_match = re.match(r"^admin_tenant_broadcast:(.+)$", data)
    if not broadcast_match:
        return False

    tenant_id = legacy.sanitize_tenant_id(broadcast_match.group(1))
    tenant = await legacy.load_tenant(tenant_id)

    if not tenant:
        await legacy.tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "租户不存在或已删除",
            "show_alert": True,
        })
        return True

    if await legacy.is_platform_tenant_blacklisted(tenant_id):
        await legacy.tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "该租户已被拉黑，禁止群发",
            "show_alert": True,
        })
        return True

    await legacy.save_apply_session(from_id, {
        "mode": "admin_tenant_broadcast",
        "step": "broadcast_input",
        "tenantId": tenant_id,
        "tenantName": tenant.get("tenantName") or tenant_id,
        "botUsername": str(((tenant.get("botInfo") or {}).get("username") or "")).strip(),
    })

    await legacy.tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_query["id"],
        "text": "请直接发送群发内容",
    })

    await legacy.tg(platform_bot_token, "sendMessage", {
        "chat_id": from_id,
        "text": (
            f"你正在给租户 {tenant.get('tenantName') or tenant_id} "
            f"(@{((tenant.get('botInfo') or {}).get('username') or tenant_id)}) 群发。\n\n"
            "请直接发送要群发的内容。"
        ),
    })
    return True
