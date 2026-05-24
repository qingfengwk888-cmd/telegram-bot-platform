import logging

from app.core.request_helpers import get_platform_bot_token
from app.telegram.api import tg
from app.utils.helpers import (
    now_ms,
    sanitize_tenant_id,
    is_primary_platform_admin,
    is_secondary_platform_admin,
)
from app.services.notice_service import get_platform_notice_target
from app.services.tenant_service import load_tenant, save_tenant, set_platform_tenant_blacklisted

logger = logging.getLogger("telegram-bot-multi-tenant-platform")


async def try_handle_platform_blacklist_command(msg: dict) -> bool:
    platform_bot_token = get_platform_bot_token()
    chat_id = int((msg.get("chat") or {}).get("id") or 0)
    text = (msg.get("text") or "").strip()
    replied = msg.get("reply_to_message")

    # 主管理员、二级管理员都可以操作
    if not (is_primary_platform_admin(chat_id) or is_secondary_platform_admin(chat_id)):
        return False

    # 只处理精确命令
    if text not in {"拉黑", "解黑"}:
        return False

    # 必须是回复某条消息
    if not replied:
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "请回复租户加入通知消息后再发送“拉黑”或“解黑”。",
        })
        return True

    target = await get_platform_notice_target(int(replied["message_id"]))
    if not target:
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "⚠️ 没有找到对应租户，请回复平台机器人发出的那条租户加入通知。",
        })
        return True

    tenant_id = sanitize_tenant_id(target.get("tenantId") or "")
    if not tenant_id:
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "⚠️ 租户标识无效。",
        })
        return True

    tenant = await load_tenant(tenant_id)
    if not tenant:
        await tg(platform_bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": f"⚠️ 租户不存在或已删除：{tenant_id}",
        })
        return True

    should_black = text == "拉黑"

    # 1. 写 Redis 黑名单
    await set_platform_tenant_blacklisted(tenant_id, should_black)

    # 2. 同步 tenant 本身字段，便于展示
    tenant["isBlacklisted"] = should_black
    tenant["updatedAt"] = now_ms()
    await save_tenant(tenant)

    # 3. 通知租户管理员（补上这段）
    tenant_admin_chat_id = int(tenant.get("adminChatId") or 0)
    if tenant_admin_chat_id:
        try:
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": tenant_admin_chat_id,
                "text": (
                    "⛔ 你已被暂停使用！。"
                    if should_black else
                    "✅ 你已恢复使用！。"
                ),
            })
        except Exception:
            logger.exception("notify tenant blacklist state failed tenantId=%s", tenant_id)

    await tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_query["id"],
        "text": "已拉黑该租户" if should_black else "已解除拉黑",
    })

    tenant_admin_chat_id = int(tenant.get("adminChatId") or 0)

    # 3. 回平台管理员确认
    await tg(platform_bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": (
            f"✅ 租户 {tenant_id} 已{'拉黑' if should_black else '解除拉黑'}。\n"
        ),
    })

    # 4. 通知租户管理员
    if tenant_admin_chat_id:
        try:
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": tenant_admin_chat_id,
                "text": (
                    "⛔ 你已被暂停使用！。"
                    if should_black else
                    "✅ 你已恢复使用。"
                ),
            })
        except Exception:
            logger.exception("notify tenant blacklist state failed tenantId=%s", tenant_id)

    return True
