async def execute_admin_tenant_broadcast(
    *,
    sender_bot: dict,
    users: list,
    broadcast_text: str,
) -> tuple[int, int]:
    from app import legacy_app as legacy

    success = 0
    failed = 0

    for u in users:
        user_id = int(u["userId"])
        try:
            await legacy.tg(sender_bot["botToken"], "sendMessage", {
                "chat_id": user_id,
                "text": broadcast_text,
            })
            success += 1
        except Exception:
            failed += 1

    return success, failed
