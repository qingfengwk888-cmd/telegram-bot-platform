import re


async def try_handle_tenant_category_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
    message: dict,
) -> bool:
    from app.telegram.api import tg
    from app.utils.helpers import sanitize_tenant_id, now_ms
    from app.services.tenant_service import load_tenant, save_tenant
    from app.services.platform_notice_view_service import refresh_tenant_detail_message

    category_match = re.match(r"^tenant_category:(local|external|other):(.+)$", data)
    if not category_match:
        return False

    category = category_match.group(1)
    tenant_id = sanitize_tenant_id(category_match.group(2))

    tenant = await load_tenant(tenant_id)
    if not tenant:
        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "租户不存在或已删除",
            "show_alert": True,
        })
        return True

    category_label_map = {
        "local": "招商(本)",
        "external": "招商(外)",
        "other": "其他",
    }
    category_label = category_label_map.get(category, "其他")

    tenant["category"] = category
    tenant["updatedAt"] = now_ms()
    await save_tenant(tenant)

    await tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_query["id"],
        "text": f"已分类为：{category_label}",
    })

    await refresh_tenant_detail_message(
        platform_bot_token=platform_bot_token,
        message=message,
        tenant=tenant,
        from_id=from_id,
    )
    return True
