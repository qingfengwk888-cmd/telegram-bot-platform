from app.telegram.keyboards import build_admin_tenant_pick_buttons_with_back


TENANT_LIST_PAGE_SIZE = 8


def clamp_page(page: int, total: int, page_size: int = TENANT_LIST_PAGE_SIZE) -> tuple[int, int]:
    total_pages = max(1, (int(total) + page_size - 1) // page_size)
    page = max(1, min(int(page or 1), total_pages))
    return page, total_pages


def slice_tenants_for_page(tenants: list[dict], page: int, page_size: int = TENANT_LIST_PAGE_SIZE) -> list[dict]:
    start = (page - 1) * page_size
    end = start + page_size
    return list(tenants[start:end])


def build_admin_tenant_paginated_pick_buttons(
    *,
    tenants: list[dict],
    page: int,
    total_pages: int,
    callback_base: str,
    back_to: str,
) -> dict:
    reply_markup = build_admin_tenant_pick_buttons_with_back(tenants, back_to)
    keyboard = list((reply_markup or {}).get("inline_keyboard") or [])

    if total_pages > 1:
        nav_row = []

        if page > 1:
            nav_row.append({
                "text": "⬅️ 上一页",
                "callback_data": f"{callback_base}:{page - 1}",
            })

        nav_row.append({
            "text": f"{page}/{total_pages}",
            "callback_data": "platform_noop",
        })

        if page < total_pages:
            nav_row.append({
                "text": "下一页 ➡️",
                "callback_data": f"{callback_base}:{page + 1}",
            })

        insert_at = len(keyboard)
        if keyboard:
            last_row = keyboard[-1]
            if any(str(btn.get("callback_data") or "").startswith("admin_tenant_back:") for btn in last_row):
                insert_at = max(0, len(keyboard) - 1)

        keyboard.insert(insert_at, nav_row)

    reply_markup["inline_keyboard"] = keyboard
    return reply_markup
