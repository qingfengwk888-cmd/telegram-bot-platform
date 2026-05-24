import re


async def try_handle_admin_tenant_back_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    data: str,
    message: dict,
) -> bool:
    from app import legacy_app as legacy

    back_match = re.match(r"^admin_tenant_back:(root|traffic|category)$", data)
    if not back_match:
        return False

    back_to = back_match.group(1)

    await legacy.tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_query["id"],
        "text": "已返回",
    })

    if not message.get("chat", {}).get("id") or not message.get("message_id"):
        return True

    if back_to == "root":
        await legacy.tg(platform_bot_token, "editMessageText", {
            "chat_id": message["chat"]["id"],
            "message_id": message["message_id"],
            "text": "🏢 所有租户\n\n请选择查看方式：",
            "reply_markup": legacy.build_admin_tenant_root_menu_buttons(),
        })
        return True

    if back_to == "traffic":
        await legacy.tg(platform_bot_token, "editMessageText", {
            "chat_id": message["chat"]["id"],
            "message_id": message["message_id"],
            "text": "🏢 所有租户\n\n请选择流量排序方式：",
            "reply_markup": legacy.build_admin_tenant_traffic_sort_buttons(),
        })
        return True

    await legacy.tg(platform_bot_token, "editMessageText", {
        "chat_id": message["chat"]["id"],
        "message_id": message["message_id"],
        "text": "🏢 所有租户\n\n请选择租户分类：",
        "reply_markup": legacy.build_admin_tenant_category_buttons(),
    })
    return True
