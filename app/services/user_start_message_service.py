from app.config import MESSAGE_MAP_TTL_SECONDS
from app.core.keys import tenant_data_key
from app.services.ad_service import load_platform_ad_config
from app.services.bot_service import save_started_user_profile
from app.services.user_service import check_bot_start_alert
from app.storage.redis_compat import redis_client
from app.telegram.api import tg
from app.telegram.formatters import build_final_welcome_text, escape_html
from app.telegram.keyboards import build_bot_reply_keyboard
from app.utils.helpers import now_ms


async def try_handle_user_start_message(
    *,
    msg: dict,
    bot: dict,
    user_id: int,
    username: str,
    first_name: str,
    last_name: str,
    display_name: str,
    user_link: str,
    text: str,
    start_payload: str,
    admin_chat_id: int,
) -> bool:
    if not text.startswith("/start"):
        return False

    started_key = tenant_data_key(bot["tenantId"], "started", user_id)
    has_started = await redis_client.get(started_key)

    if start_payload:
        await redis_client.set(
            tenant_data_key(bot["tenantId"], "source", user_id),
            start_payload,
        )

    bot_username = str(((bot.get("botInfo") or {}).get("username") or "")).strip()

    user_profile = {
        "userId": int(user_id),
        "username": username,
        "firstName": first_name,
        "lastName": last_name,
        "displayName": display_name,
        "source": start_payload or "direct",
        "startedAt": now_ms(),

        # 新增：记录是从哪个机器人启动的
        "botId": str(bot.get("botId") or "").strip(),
        "botUsername": bot_username,
        "tenantId": str(bot.get("tenantId") or "").strip(),
    }
    await save_started_user_profile(bot["botId"], user_profile)

    # 每次 /start 都发欢迎语和按钮
    ad_config = await load_platform_ad_config()

    await tg(bot["botToken"], "sendMessage", {
        "chat_id": user_id,
        "text": build_final_welcome_text(bot, ad_config),
        "parse_mode": "HTML",
        "link_preview_options": {
            "is_disabled": True
        },
        "reply_markup": build_bot_reply_keyboard(bot)
    })



    # 只有第一次 /start 才通知管理员
    if not has_started:
        source_text = start_payload or "direct"

        admin_text = (
            "🟢 <b>新用户启动</b>\n"
            "━━━━━━━━━━\n"
            f"👤 用户：{user_link}\n"
            f"🆔 UID：<code>{user_id}</code>\n"
            f"📍 来源：<code>{escape_html(source_text)}</code>"
        )

        sent = await tg(bot["botToken"], "sendMessage", {
            "chat_id": admin_chat_id,
            "text": admin_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        })

        admin_message_id = ((sent or {}).get("result") or {}).get("message_id")
        if admin_message_id:
            await redis_client.set(
                tenant_data_key(bot["tenantId"], "msg", admin_message_id),
                str(user_id),
                ex=MESSAGE_MAP_TTL_SECONDS,
            )

        await redis_client.set(started_key, "1")
        await check_bot_start_alert(bot, user_profile)

    return True
