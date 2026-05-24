import logging

from app.core.keys import tenant_data_key
from app.services.bot_service import set_bot_user_blacklisted
from app.telegram.api import tg
from app.storage.redis_compat import redis_client

logger = logging.getLogger(__name__)


async def try_handle_bot_user_blacklist_command(bot: dict, msg: dict) -> bool:
    bot_token = bot["botToken"]
    admin_chat_id = int(bot["adminChatId"])
    chat_id = int((msg.get("chat") or {}).get("id") or 0)
    text = (msg.get("text") or "").strip()
    replied = msg.get("reply_to_message")

    # 只有租户管理员自己的消息才处理
    if int(chat_id) != int(admin_chat_id):
        return False

    # 只处理拉黑 / 解黑
    if text not in {"拉黑", "解黑"}:
        return False

    # 必须回复某条用户消息
    if not replied:
        await tg(bot_token, "sendMessage", {
            "chat_id": admin_chat_id,
            "text": "请回复某个用户的启动消息或用户消息，然后发送“拉黑”或“解黑”。",
        })
        return True

    # 用管理员端那条转发消息的 message_id 找目标用户
    target_user_id = await redis_client.get(
        tenant_data_key(bot["tenantId"], "msg", replied["message_id"])
    )

    if not target_user_id:
        await tg(bot_token, "sendMessage", {
            "chat_id": admin_chat_id,
            "text": "⚠️ 没有找到对应用户，请回复机器人转发给你的那条用户消息。",
        })
        return True

    target_user_id = int(target_user_id)
    should_black = text == "拉黑"

    await set_bot_user_blacklisted(bot["botId"], target_user_id, should_black)

    await tg(bot_token, "sendMessage", {
        "chat_id": admin_chat_id,
        "text": f"✅ 用户 UID:{target_user_id} 已{'拉黑' if should_black else '解除拉黑'}。",
    })

    if should_black:
        try:
            await tg(bot_token, "sendMessage", {
                "chat_id": target_user_id,
                "text": "⛔ 你已被管理员暂停使用。",
            })
        except Exception:
            logger.exception(
                "notify blacklisted user failed botId=%s userId=%s",
                bot["botId"],
                target_user_id,
            )

    return True
