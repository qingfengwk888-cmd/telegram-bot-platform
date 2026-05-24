async def try_handle_platform_global_broadcast_target_select_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
) -> bool:
    from app import legacy_app as legacy

    if not data.startswith("platform_global_broadcast_target:"):
        return False

    target_type = data.split(":", 1)[1].strip()

    if target_type not in {"tenants", "tenant_users", "all_people"}:
        await legacy.tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "无效的群发范围",
            "show_alert": True,
        })
        return True

    await legacy.save_apply_session(from_id, {
        "mode": "platform_global_broadcast",
        "step": "broadcast_input",
        "targetType": target_type,
    })

    target_label_map = {
        "tenants": "全部租户",
        "tenant_users": "全部租户的用户",
        "all_people": "所有人",
    }

    await legacy.tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_query["id"],
        "text": f"已选择：{target_label_map[target_type]}",
    })

    await legacy.tg(platform_bot_token, "sendMessage", {
        "chat_id": from_id,
        "text": f"你正在给【{target_label_map[target_type]}】群发。\n\n请直接发送群发内容。",
    })
    return True
