from app.core.keys import tenant_data_key
from app.services.bot_user_blacklist_command_service import try_handle_bot_user_blacklist_command
from app.services.lock_service import get_current_lock, set_current_lock
from app.storage.redis_compat import redis_client
from app.telegram.api import tg


async def handle_admin_message(msg: dict, bot: dict) -> None:
    admin_chat_id = int(bot["adminChatId"])

    if await try_handle_bot_user_blacklist_command(bot, msg):
        return

    replied = msg.get("reply_to_message")
    if replied:
        target_user_id = await redis_client.get(
            tenant_data_key(bot["tenantId"], "msg", replied["message_id"])
        )
        if not target_user_id:
            await tg(bot["botToken"], "sendMessage", {
                "chat_id": admin_chat_id,
                "text": "⚠️ 没有找到对应用户，请回复机器人转发给你的那条消息。",
            })
            return

        await tg(bot["botToken"], "copyMessage", {
            "chat_id": int(target_user_id),
            "from_chat_id": admin_chat_id,
            "message_id": msg["message_id"],
        })

        await set_current_lock(bot["tenantId"], admin_chat_id, int(target_user_id))

        await tg(bot["botToken"], "sendMessage", {
            "chat_id": admin_chat_id,
            "text": f"✅ 已切换当前聊天用户为 UID:{target_user_id}（10分钟内有效）",
        })
        return

    locked_user_id = await get_current_lock(bot["tenantId"], admin_chat_id)
    if not locked_user_id:
        await tg(bot["botToken"], "sendMessage", {
            "chat_id": admin_chat_id,
            "text": "⚠️ 请先回复某条用户消息来锁定聊天对象，然后才能直接连续发送。",
        })
        return

    await tg(bot["botToken"], "copyMessage", {
        "chat_id": locked_user_id,
        "from_chat_id": admin_chat_id,
        "message_id": msg["message_id"],
    })
