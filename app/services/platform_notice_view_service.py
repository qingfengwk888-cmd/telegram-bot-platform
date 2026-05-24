import logging

from app.config import PLATFORM_SECONDARY_ADMIN_CHAT_IDS
from app.services.notice_service import map_platform_notice_message
from app.services.tenant_service import list_bots_by_tenant_id, list_started_users_by_tenant_id_for_admin
from app.telegram.api import tg
from app.telegram.formatters import (
    escape_html,
    format_started_users_text,
    format_tenant_category_text,
    format_tenant_summary_text,
)
from app.utils.helpers import build_user_link
from app.telegram.keyboards import (
    build_new_tenant_notice_buttons,
    build_tenant_category_buttons,
    build_tenant_detail_action_buttons,
)

logger = logging.getLogger(__name__)


def is_new_tenant_notice_text(text: str) -> bool:
    text = str(text or "")
    return (
        "🟢 有新租户加入" in text
        or "🟢 <b>有新租户加入</b>" in text
        or "🟢 有新机器人接入" in text
        or "🟢 <b>有新机器人接入</b>" in text
    )


async def refresh_tenant_detail_message(
    *,
    platform_bot_token: str,
    message: dict,
    tenant: dict,
    from_id: int,
) -> None:
    if not message.get("chat", {}).get("id") or not message.get("message_id"):
        return

    tenant_id = str(tenant.get("tenantId") or "").strip()
    original_text = str(message.get("text") or "")

    # 1) 如果当前消息是“新租户/新机器人接入通知”页，只刷新按钮状态，不改正文
    if is_new_tenant_notice_text(original_text):
        await tg(platform_bot_token, "editMessageReplyMarkup", {
            "chat_id": message["chat"]["id"],
            "message_id": message["message_id"],
            "reply_markup": build_new_tenant_notice_buttons(tenant),
        })
        return

    # 2) 如果当前消息是租户详情页，刷新正文 + 按钮
    bots = await list_bots_by_tenant_id(tenant_id)
    users = await list_started_users_by_tenant_id_for_admin(tenant_id)

    await tg(platform_bot_token, "editMessageText", {
        "chat_id": message["chat"]["id"],
        "message_id": message["message_id"],
        "text": (
            (await format_tenant_summary_text(tenant, bots))
            + "\n\n"
            + format_started_users_text(tenant, users)
            + "\n\n"
            + format_tenant_category_text(tenant)
        ),
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": build_tenant_detail_action_buttons(tenant_id, from_id),
    })


async def notify_new_bot_connected(
    *,
    platform_bot_token: str,
    platform_admin_chat_id: int,
    tenant_id: str,
    tenant_name: str,
    chat_id: int,
    username: str,
    display_name: str,
    bot: dict,
) -> None:
    try:
        bot_username = str(((bot.get("botInfo") or {}).get("username") or "")).strip()
        user_link = build_user_link(int(chat_id), username, display_name)

        notice_text = (
            "🟢 <b>新机器人接入</b>\n"
            "━━━━━━━━━━\n"
            f"👤 租户用户：{user_link}\n"
            f'💬 Chat ID：<a href="tg://user?id={chat_id}"><code>{chat_id}</code></a>\n'
            f"🏢 租户名称：<b>{escape_html(tenant_name)}</b>\n"
            f"🤖 机器人：<b>{escape_html('@' + bot_username)}</b>"
        )

        reply_markup = {
            "inline_keyboard": build_tenant_category_buttons(tenant_id)
        }

        if platform_admin_chat_id:
            try:
                notify_res = await tg(platform_bot_token, "sendMessage", {
                    "chat_id": platform_admin_chat_id,
                    "text": notice_text,
                    "parse_mode": "HTML",
                    "reply_markup": reply_markup,
                })

                if notify_res.get("result", {}).get("message_id"):
                    await map_platform_notice_message(
                        int(notify_res["result"]["message_id"]),
                        tenant_id,
                        chat_id,
                    )
            except Exception:
                logger.exception(
                    "notify primary platform admin failed tenant_id=%s chat_id=%s",
                    tenant_id,
                    platform_admin_chat_id,
                )

        for secondary_chat_id in PLATFORM_SECONDARY_ADMIN_CHAT_IDS:
            try:
                await tg(platform_bot_token, "sendMessage", {
                    "chat_id": secondary_chat_id,
                    "text": notice_text,
                    "parse_mode": "HTML",
                    "reply_markup": reply_markup,
                })
            except Exception:
                logger.exception(
                    "notify secondary platform admin failed tenant_id=%s chat_id=%s",
                    tenant_id,
                    secondary_chat_id,
                )
    except Exception:
        logger.exception("notify_new_bot_connected task failed")


async def refresh_tenant_latest_bot_id(tenant_id: str) -> None:
    # 数据库版不再需要单独维护 latest_bot_id key。
    # 最新 bot 通过 bots.created_at_ms 排序实时计算。
    return None
