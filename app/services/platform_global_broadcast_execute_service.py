async def execute_platform_global_broadcast(
    *,
    platform_bot_token: str,
    broadcast_text: str,
    target_type: str,
) -> tuple[int, int, int]:
    from app import legacy_app as legacy

    tenant_ids = await legacy.get_tenant_index()

    total_target = 0
    success = 0
    failed = 0

    # 防止同一个 chat_id 被重复发送
    sent_platform_chat_ids = set()
    sent_tenant_user_pairs = set()   # (tenant_id, user_id)

    for tenant_id in tenant_ids:
        tenant = await legacy.load_tenant(tenant_id)
        if not tenant:
            continue

        if await legacy.is_platform_tenant_blacklisted(tenant_id):
            continue

        admin_chat_id = int(tenant.get("adminChatId") or 0)
        users = await legacy.list_started_users_by_tenant_id(tenant_id)

        sender_bot = await legacy.pick_sender_bot_for_tenant(tenant_id)
        tenant_bot_token = str(sender_bot.get("botToken") or "").strip() if sender_bot else ""

        if target_type == "tenants":
            if admin_chat_id and admin_chat_id not in sent_platform_chat_ids:
                sent_platform_chat_ids.add(admin_chat_id)
                total_target += 1
                try:
                    await legacy.tg(platform_bot_token, "sendMessage", {
                        "chat_id": admin_chat_id,
                        "text": broadcast_text,
                    })
                    success += 1
                except Exception:
                    failed += 1

        elif target_type == "tenant_users":
            if not tenant_bot_token:
                continue

            for u in users:
                user_id = int(u.get("userId") or 0)
                if not user_id:
                    continue

                pair_key = (tenant_id, user_id)
                if pair_key in sent_tenant_user_pairs:
                    continue

                sent_tenant_user_pairs.add(pair_key)
                total_target += 1

                try:
                    await legacy.tg(tenant_bot_token, "sendMessage", {
                        "chat_id": user_id,
                        "text": broadcast_text,
                    })
                    success += 1
                except Exception:
                    failed += 1

        elif target_type == "all_people":
            if admin_chat_id and admin_chat_id not in sent_platform_chat_ids:
                sent_platform_chat_ids.add(admin_chat_id)
                total_target += 1
                try:
                    await legacy.tg(platform_bot_token, "sendMessage", {
                        "chat_id": admin_chat_id,
                        "text": broadcast_text,
                    })
                    success += 1
                except Exception:
                    failed += 1

            if not tenant_bot_token:
                continue

            for u in users:
                user_id = int(u.get("userId") or 0)
                if not user_id:
                    continue

                pair_key = (tenant_id, user_id)
                if pair_key in sent_tenant_user_pairs:
                    continue

                sent_tenant_user_pairs.add(pair_key)
                total_target += 1

                try:
                    await legacy.tg(tenant_bot_token, "sendMessage", {
                        "chat_id": user_id,
                        "text": broadcast_text,
                    })
                    success += 1
                except Exception:
                    failed += 1

    return total_target, success, failed
