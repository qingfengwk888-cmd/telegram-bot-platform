from typing import List

from app.core.logger import logger
from app.core.request_helpers import get_platform_bot_token
from app.core.keys import tenant_data_key

import re

from app.telegram.api import tg
from app.telegram.keyboards import build_profile_buttons


from app.storage.redis_compat import redis_client
from app.storage.repository import (
    is_platform_tenant_blacklisted_db,
    set_platform_tenant_blacklisted_db,
    is_bot_user_blacklisted_db,
    set_bot_user_blacklisted_db,
    list_bot_blacklisted_users_db,
)
from app.utils.helpers import sanitize_tenant_id, escape_html, format_date_ymd, now_ms, is_primary_platform_admin, is_secondary_platform_admin
from app.services.notice_service import get_platform_notice_target


def bot_user_black_key(bot_id: str, user_id: int) -> str:
    return f"b:{bot_id}:black:user:{int(user_id)}"


def bot_user_blacklist_set_key(bot_id: str) -> str:
    return f"b:{bot_id}:black:users"


def platform_tenant_black_key(tenant_id: str) -> str:
    return f"platform:black:tenant:{sanitize_tenant_id(tenant_id)}"


async def is_tenant_user_blacklisted(tenant_id: str, user_id: int) -> bool:
    # 临时兼容：租户维度用户黑名单目前仍走 legacy 逻辑
    from app import legacy_app
    return await legacy_app.is_tenant_user_blacklisted(tenant_id, user_id)


async def list_blacklisted_users_by_tenant_id(tenant_id: str) -> List[dict]:
    from app import legacy_app
    return await legacy_app.list_blacklisted_users_by_tenant_id(tenant_id)


async def list_blacklisted_users(bot_id: str) -> List[dict]:
    return await list_bot_blacklisted_users_db(bot_id)


def format_blacklisted_users_text(bot: dict, users: List[dict]) -> str:
    bot_username = str(((bot.get("botInfo") or {}).get("username") or "")).strip()
    bot_show = f"@{bot_username}" if bot_username else str(bot.get("botId") or "")

    if not users:
        return f"🚫 <b>{escape_html(bot_show)} 黑名单</b>\n\n当前暂无黑名单用户。"

    lines = [
        f"🚫 <b>{escape_html(bot_show)} 黑名单</b>",
        "",
        f"共 {len(users)} 个用户",
        "",
    ]

    for idx, u in enumerate(users[:100], start=1):
        user_id = int(u.get("userId") or 0)
        username = str(u.get("username") or "").strip()
        first_name = str(u.get("firstName") or "").strip()
        last_name = str(u.get("lastName") or "").strip()
        started_date = format_date_ymd(u.get("startedAt"))

        display_name = (
            f"@{username}"
            if username else
            (" ".join([x for x in [first_name, last_name] if x]).strip() or f"UID:{user_id}")
        )

        lines.append(
            f"{idx}. <a href=\"tg://user?id={user_id}\">{escape_html(display_name)}</a> "
            f"| UID:<code>{user_id}</code> | {started_date}"
        )

    if len(users) > 100:
        lines.append("")
        lines.append(f"仅显示前 100 条，共 {len(users)} 条")

    return "\n".join(lines)


def format_tenant_blacklisted_users_text(tenant: dict, users: List[dict]) -> str:
    tenant_name = str(tenant.get("tenantName") or tenant.get("tenantId") or "").strip()

    if not users:
        return f"🚫 <b>{escape_html(tenant_name)} 黑名单用户</b>\n\n当前暂无黑名单用户。"

    lines = [
        f"🚫 <b>{escape_html(tenant_name)} 黑名单用户</b>",
        "",
        f"共 {len(users)} 个用户",
        "",
    ]

    for idx, u in enumerate(users[:100], start=1):
        user_id = int(u.get("userId") or 0)
        username = str(u.get("username") or "").strip()
        first_name = str(u.get("firstName") or "").strip()
        last_name = str(u.get("lastName") or "").strip()
        bot_username = str(u.get("botUsername") or "").strip()
        started_date = format_date_ymd(u.get("startedAt"))

        display_name = (
            f"@{username}"
            if username else
            (" ".join([x for x in [first_name, last_name] if x]).strip() or f"UID:{user_id}")
        )

        bot_show = f"@{bot_username}" if bot_username else str(u.get("botId") or "")

        lines.append(
            f"{idx}. <a href=\"tg://user?id={user_id}\">{escape_html(display_name)}</a> "
            f"| UID:<code>{user_id}</code> | {escape_html(bot_show)} | {started_date}"
        )

    if len(users) > 100:
        lines.append("")
        lines.append(f"仅显示前 100 条，共 {len(users)} 条")

    return "\n".join(lines)


