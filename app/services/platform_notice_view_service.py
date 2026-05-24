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
    chat_id: int | None = None,
    message_id: int | None = None,
    tenant_id: str | None = None,
    tenant: dict | None = None,
    message: dict | None = None,
    from_id: int | None = None,
    callback_query: dict | None = None,
    **_ignored,
) -> None:
    from app.telegram.api import tg
    from app.services.tenant_service import (
        load_tenant,
        list_bots_by_tenant_id,
        list_started_users_by_tenant_id_for_admin,
    )
    from app.telegram.formatters import (
        format_tenant_summary_text,
        format_started_users_text,
        format_tenant_category_text,
    )
    from app.telegram.keyboards import build_tenant_detail_action_buttons

    if message is None and callback_query:
        message = callback_query.get("message") or {}

    if chat_id is None and message:
        chat_id = (message.get("chat") or {}).get("id")

    if message_id is None and message:
        message_id = message.get("message_id")

    if tenant_id is None and tenant:
        tenant_id = tenant.get("tenantId")

    if tenant_id is None:
        return

    if tenant is None:
        tenant = await load_tenant(tenant_id)
    if not tenant:
        return

    if not chat_id or not message_id:
        return

    bots = await list_bots_by_tenant_id(tenant_id)
    users = await list_started_users_by_tenant_id_for_admin(tenant_id)

    page = 1
    page_size = 25
    total = len(users)
    total_pages = max(1, (total + page_size - 1) // page_size)

    def build_text(limit: int) -> str:
        display_users = users[:limit]
        current_total_pages = max(1, (total + limit - 1) // limit)

        page_text = (
            f"\n\n📄 当前第 1/{current_total_pages} 页，共 {total} 条启动记录。"
            if total > limit
            else ""
        )

        return (
            "__SUMMARY__"
            + "\n\n"
            + format_started_users_text(tenant, display_users)
            + page_text
            + "\n\n"
            + format_tenant_category_text(tenant)
        )

    summary_text = await format_tenant_summary_text(tenant)

    # Telegram 单条消息限制约 4096；留余量，避免昵称/source 过长导致失败。
    text_body = build_text(page_size).replace("__SUMMARY__", summary_text)
    while len(text_body) > 3400 and page_size > 5:
        page_size -= 5
        total_pages = max(1, (total + page_size - 1) // page_size)
        text_body = build_text(page_size).replace("__SUMMARY__", summary_text)

    reply_markup = build_tenant_detail_action_buttons(tenant_id, chat_id)
    keyboard = list((reply_markup or {}).get("inline_keyboard") or [])

    if total_pages > 1:
        keyboard.append([
            {
                "text": f"{page}/{total_pages}",
                "callback_data": "platform_noop",
            },
            {
                "text": "下一页 ➡️",
                "callback_data": f"admin_tenant:view:{tenant_id}:2",
            },
        ])

    reply_markup["inline_keyboard"] = keyboard

    await tg(platform_bot_token, "editMessageText", {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text_body,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": reply_markup,
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
