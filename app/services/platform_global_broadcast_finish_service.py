async def finish_platform_global_broadcast_confirm(
    *,
    platform_bot_token: str,
    from_id: int,
    message: dict,
    target_type: str,
    total_target: int,
    success: int,
    failed: int,
) -> None:
    from app import legacy_app as legacy

    await legacy.clear_apply_session(from_id)

    if message.get("chat", {}).get("id") and message.get("message_id"):
        try:
            await legacy.tg(platform_bot_token, "editMessageReplyMarkup", {
                "chat_id": message["chat"]["id"],
                "message_id": message["message_id"],
                "reply_markup": {"inline_keyboard": []},
            })
        except Exception:
            pass

    target_label_map = {
        "tenants": "全部租户",
        "tenant_users": "全部租户的用户",
        "all_people": "所有人",
    }

    await legacy.tg(platform_bot_token, "sendMessage", {
        "chat_id": from_id,
        "text": (
            "🌐 全部群发完成\n"
            f"范围：{target_label_map.get(target_type, target_type)}\n"
            f"目标人数：{total_target}\n"
            f"成功：{success}\n"
            f"失败：{failed}"
        ),
    })
