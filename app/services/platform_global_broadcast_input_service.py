from app.telegram.api import tg
from app.telegram.keyboards import build_global_broadcast_confirm_buttons
from app.services.apply_service import clear_apply_session, save_apply_session
from app.services.tenant_service import (
    get_tenant_index,
    load_tenant,
    list_started_users_by_tenant_id,
    is_platform_tenant_blacklisted,
)


async def try_handle_platform_global_broadcast_input(
    *,
    platform_bot_token: str,
    chat_id: int,
    text: str,
    session: dict,
) -> bool:
    if not session or session.get("mode") != "platform_global_broadcast":
        return False

    if session.get("step") != "broadcast_input":
        return False

    broadcast_text = text.strip()
    target_type = str(session.get("targetType") or "").strip()

    if not broadcast_text:
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "群发内容不能为空。",
        })
        return True

    target_label_map = {
        "tenants": "全部租户",
        "tenant_users": "全部租户的用户",
        "all_people": "所有人",
    }

    if target_type not in target_label_map:
        await clear_apply_session(chat_id)
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "群发范围无效，请重新选择。",
        })
        return True

    tenant_ids = await get_tenant_index()

    total_target = 0
    available_tenant_count = 0
    counted_platform_chat_ids = set()
    counted_tenant_user_pairs = set()

    for tenant_id in tenant_ids:
        tenant = await load_tenant(tenant_id)
        if not tenant:
            continue

        if await is_platform_tenant_blacklisted(tenant_id):
            continue

        admin_chat_id = int(tenant.get("adminChatId") or 0)
        users = await list_started_users_by_tenant_id(tenant_id)

        tenant_has_target = False

        if target_type == "tenants":
            if admin_chat_id and admin_chat_id not in counted_platform_chat_ids:
                counted_platform_chat_ids.add(admin_chat_id)
                total_target += 1
                tenant_has_target = True

        elif target_type == "tenant_users":
            for u in users:
                user_id = int(u.get("userId") or 0)
                if not user_id:
                    continue

                pair_key = (tenant_id, user_id)
                if pair_key in counted_tenant_user_pairs:
                    continue

                counted_tenant_user_pairs.add(pair_key)
                total_target += 1
                tenant_has_target = True

        elif target_type == "all_people":
            if admin_chat_id and admin_chat_id not in counted_platform_chat_ids:
                counted_platform_chat_ids.add(admin_chat_id)
                total_target += 1
                tenant_has_target = True

            for u in users:
                user_id = int(u.get("userId") or 0)
                if not user_id:
                    continue

                pair_key = (tenant_id, user_id)
                if pair_key in counted_tenant_user_pairs:
                    continue

                counted_tenant_user_pairs.add(pair_key)
                total_target += 1
                tenant_has_target = True

        if tenant_has_target:
            available_tenant_count += 1

    if total_target <= 0:
        await clear_apply_session(chat_id)
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "当前没有可群发的目标用户。",
        })
        return True

    session["step"] = "broadcast_confirm"
    session["broadcastText"] = broadcast_text
    session["targetCount"] = total_target
    session["tenantCount"] = available_tenant_count
    await save_apply_session(chat_id, session)

    await tg(platform_bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": (
            "🌐 即将执行全部群发\n"
            f"群发范围：{target_label_map[target_type]}\n"
            f"目标租户数：{available_tenant_count}\n"
            f"目标人数：{total_target}\n\n"
            f"群发内容：\n{broadcast_text}\n\n"
            "请确认是否发送。"
        ),
        "reply_markup": build_global_broadcast_confirm_buttons(),
    })
    return True
