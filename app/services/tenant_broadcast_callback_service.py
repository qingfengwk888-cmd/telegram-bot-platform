import logging

from app.services.apply_service import clear_apply_session, load_apply_session
from app.services.blacklist_service import is_tenant_user_blacklisted
from app.services.bot_service import list_started_users, load_bot
from app.services.tenant_service import is_platform_tenant_blacklisted, load_tenant
from app.telegram.api import tg
from app.utils.helpers import sanitize_tenant_id

logger = logging.getLogger(__name__)


async def try_handle_tenant_broadcast_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
    callback_id: str,
) -> bool:
    if data == "tenant_broadcast_cancel":
        await clear_apply_session(from_id)

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "已取消群发",
        })

        if callback_query.get("message", {}).get("chat", {}).get("id") and callback_query.get("message", {}).get("message_id"):
            try:
                await tg(platform_bot_token, "editMessageReplyMarkup", {
                    "chat_id": callback_query["message"]["chat"]["id"],
                    "message_id": callback_query["message"]["message_id"],
                    "reply_markup": {"inline_keyboard": []},
                })
            except Exception:
                pass
        return True


    if data == "tenant_broadcast_confirm":
        session = await load_apply_session(from_id)
        if not session or session.get("mode") != "tenant_broadcast" or session.get("step") != "broadcast_confirm":
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "群发会话已失效，请重新操作",
                "show_alert": True,
            })
            return True

        tenant_id = sanitize_tenant_id(session.get("tenantId") or "")
        sender_bot_id = sanitize_tenant_id(session.get("senderBotId") or session.get("botId") or "")
        broadcast_text = str(session.get("broadcastText") or "").strip()

        if not tenant_id or not sender_bot_id or not broadcast_text:
            await clear_apply_session(from_id)
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "群发参数无效，请重新操作",
                "show_alert": True,
            })
            return True

        tenant = await load_tenant(tenant_id)
        if not tenant:
            await clear_apply_session(from_id)
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "租户不存在或已删除",
                "show_alert": True,
            })
            return True

        if int(tenant.get("adminChatId", 0)) != int(from_id):
            await clear_apply_session(from_id)
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "你没有权限操作这个机器人",
                "show_alert": True,
            })
            return True

        if await is_platform_tenant_blacklisted(tenant_id):
            await clear_apply_session(from_id)
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "该租户已被平台拉黑，禁止群发",
                "show_alert": True,
            })
            return True

        sender_bot = await load_bot(sender_bot_id)
        if not sender_bot or not str(sender_bot.get("botToken") or "").strip():
            await clear_apply_session(from_id)
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "发送机器人不存在或不可用",
                "show_alert": True,
            })
            return True

        if str(sender_bot.get("tenantId") or "").strip() != tenant_id:
            await clear_apply_session(from_id)
            await tg(platform_bot_token, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "机器人不属于当前租户",
                "show_alert": True,
            })
            return True

        await tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "开始群发",
        })

        users = await list_started_users(sender_bot_id)
        success = 0
        failed = 0

        for u in users:
            user_id = int(u.get("userId") or 0)
            if not user_id:
                continue

            if await is_tenant_user_blacklisted(tenant_id, user_id):
                continue

            try:
                await tg(sender_bot["botToken"], "sendMessage", {
                    "chat_id": user_id,
                    "text": broadcast_text,
                })
                success += 1
            except Exception:
                logger.exception(
                    "tenant broadcast send failed tenant_id=%s sender_bot_id=%s user_id=%s",
                    tenant_id,
                    sender_bot_id,
                    user_id,
                )
                failed += 1

        await clear_apply_session(from_id)

        if callback_query.get("message", {}).get("chat", {}).get("id") and callback_query.get("message", {}).get("message_id"):
            try:
                await tg(platform_bot_token, "editMessageReplyMarkup", {
                    "chat_id": callback_query["message"]["chat"]["id"],
                    "message_id": callback_query["message"]["message_id"],
                    "reply_markup": {"inline_keyboard": []},
                })
            except Exception:
                pass

        sender_bot_username = str(((sender_bot.get("botInfo") or {}).get("username") or "")).strip()

        await tg(platform_bot_token, "sendMessage", {
            "chat_id": from_id,
            "text": (
                "📣 群发完成\n"
                f"机器人：@{sender_bot_username or sender_bot_id}\n"
                f"目标人数：{len(users)}\n"
                f"成功：{success}\n"
                f"失败：{failed}"
            ),
        })
        return True

    return False
