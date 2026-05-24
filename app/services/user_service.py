import time
from typing import Optional

from app.config import (
    START_ALERT_WINDOW_SECONDS,
    START_ALERT_THRESHOLD,
    START_ALERT_COOLDOWN_SECONDS,
    PLATFORM_SECONDARY_ADMIN_CHAT_IDS,
)
from app.core.logger import logger
from app.storage.redis_compat import redis_client
from app.telegram.api import tg
from app.utils.helpers import now_ms, escape_html, sanitize_tenant_id


def find_bot_button_reply(bot: dict, incoming_text: str) -> Optional[str]:
    incoming_text = str(incoming_text or "").strip()
    if not incoming_text:
        return None

    reply_map = bot.get("welcomeButtonReplyMap") or {}
    reply = str(reply_map.get(incoming_text) or "").strip()
    if reply:
        return reply

    # 兼容老数据，兜底回退
    buttons = bot.get("welcomeButtons") or []
    for row in buttons:
        if not isinstance(row, list):
            continue
        for btn in row:
            if not isinstance(btn, dict):
                continue
            btn_text = str(btn.get("text") or "").strip()
            btn_reply = str(btn.get("reply") or "").strip()
            if btn_text and incoming_text == btn_text and btn_reply:
                return btn_reply

    return None


def bot_user_profile_key(bot_id: str, user_id: int) -> str:
    return f"b:{bot_id}:profile:{int(user_id)}"


async def check_bot_start_alert(bot: dict, user_profile: dict) -> None:
    bot_id = sanitize_tenant_id(bot.get("botId") or "")
    if not bot_id:
        return

    started_at = int(user_profile.get("startedAt") or 0)
    if not started_at:
        return

    window_key = bot_start_alert_window_key(bot_id)
    cooldown_key = bot_start_alert_cooldown_key(bot_id)

    now_ts = int(time.time())
    window_start_ts = now_ts - START_ALERT_WINDOW_SECONDS

    await redis_client.zadd(window_key, {str(user_profile["userId"]): now_ts})
    await redis_client.zremrangebyscore(window_key, 0, window_start_ts - 1)

    started_count = int(await redis_client.zcard(window_key) or 0)

    if started_count <= START_ALERT_THRESHOLD:
        return

    cooldown_ok = await redis_client.set(
        cooldown_key,
        "1",
        ex=START_ALERT_COOLDOWN_SECONDS,
        nx=True,
    )
    if not cooldown_ok:
        return

    tenant_id = str(bot.get("tenantId") or "").strip()
    tenant_name = str(bot.get("tenantName") or tenant_id or bot_id).strip()
    bot_username = str(((bot.get("botInfo") or {}).get("username") or "")).strip()
    bot_show = f"@{bot_username}" if bot_username else bot_id

    text = (
        "⚠️ <b>启动异常预警</b>\n"
        "━━━━━━━━━━\n"
        f"🏢 租户：<b>{escape_html(tenant_name)}</b>\n"
        f"🆔 tenantId：<code>{escape_html(tenant_id)}</code>\n"
        f"🤖 机器人：<b>{escape_html(bot_show)}</b>\n"
        f"🆔 botId：<code>{escape_html(bot_id)}</code>\n"
        f"📈 近10分钟启动人数：<b>{started_count}</b>\n"
        "⚠️ 该机器人近10分钟启动人数过高，存在刷量风险。"
    )

    reply_markup = {
        "inline_keyboard": [[
            {"text": "查看租户详情", "callback_data": f"admin_tenant:view:{tenant_id}"}
        ]]
    }

    platform_bot_token = get_platform_bot_token()
    target_admin_ids = set()

    primary_admin_chat_id = get_platform_admin_chat_id()
    if primary_admin_chat_id:
        target_admin_ids.add(int(primary_admin_chat_id))

    for admin_id in PLATFORM_SECONDARY_ADMIN_CHAT_IDS:
        if admin_id:
            target_admin_ids.add(int(admin_id))

    for admin_id in target_admin_ids:
        try:
            await tg(platform_bot_token, "sendMessage", {
                "chat_id": admin_id,
                "text": text,
                "parse_mode": "HTML",
                "reply_markup": reply_markup,
            })
        except Exception:
            logger.exception(
                "notify start alert failed botId=%s chat_id=%s",
                bot_id,
                admin_id,
            )


def _legacy():
    from app import legacy_app
    return legacy_app


def get_platform_bot_token() -> str:
    return _legacy().get_platform_bot_token()


def get_platform_admin_chat_id() -> int:
    return _legacy().get_platform_admin_chat_id()


def bot_start_alert_window_key(bot_id: str) -> str:
    return _legacy().bot_start_alert_window_key(bot_id)


def bot_start_alert_cooldown_key(bot_id: str) -> str:
    return _legacy().bot_start_alert_cooldown_key(bot_id)
