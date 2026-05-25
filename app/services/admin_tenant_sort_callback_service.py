import re


async def try_handle_admin_tenant_sort_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    data: str,
    message: dict,
) -> bool:
    from app.telegram.api import tg
    from app.services.tenant_service import get_tenant_index, load_tenant
    from app.services.platform_dashboard_view_service import format_simple_tenant_list_text
    from app.services.admin_tenant_list_pagination_service import clamp_page, slice_tenants_for_page, build_admin_tenant_paginated_pick_buttons

    sort_match = re.match(r"^admin_tenant_sort:(asc|desc)(?::(\\d+))?$", data)
    if not sort_match:
        return False

    sort_type = sort_match.group(1)
    page = max(1, int(sort_match.group(2) or 1))

    ids = await get_tenant_index()
    tenants = []

    for tenant_id in ids:
        tenant = await load_tenant(tenant_id)
        if not tenant:
            continue
        tenant["_started_count"] = int(tenant.get("startedUserCount") or 0)
        tenants.append(tenant)

    tenants.sort(
        key=lambda x: int(x.get("_started_count", 0)),
        reverse=(sort_type == "desc")
    )

    title = (
        "🏢 所有租户 · 按流量从高到低"
        if sort_type == "desc"
        else "🏢 所有租户 · 按流量从低到高"
    )

    await tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_query["id"],
        "text": "已完成排序",
    })

    if not message.get("chat", {}).get("id") or not message.get("message_id"):
        return True

    page, total_pages = clamp_page(page, len(tenants))
    display_tenants = slice_tenants_for_page(tenants, page)
    page_title = (
        f"{title}\n📄 第 {page}/{total_pages} 页，共 {len(tenants)} 个租户"
        if total_pages > 1
        else title
    )

    await tg(platform_bot_token, "editMessageText", {
        "chat_id": message["chat"]["id"],
        "message_id": message["message_id"],
        "text": format_simple_tenant_list_text(page_title, display_tenants),
        "parse_mode": "HTML",
        "reply_markup": build_admin_tenant_paginated_pick_buttons(
            tenants=display_tenants,
            page=page,
            total_pages=total_pages,
            callback_base=f"admin_tenant_sort:{sort_type}",
            back_to="admin_tenant_back:traffic",
        ),
    })
    return True
