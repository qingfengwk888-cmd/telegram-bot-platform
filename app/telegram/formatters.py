import html
from collections import OrderedDict
from typing import List, Optional

from app.config import DEFAULT_WELCOME_TEXT
from app.utils.helpers import escape_html, format_date_ymd

def _legacy():
    from app import legacy_app
    return legacy_app


# 注意：部分 formatter 暂时仍依赖 legacy_app 内的查询函数。
# 下一步正式替换 import 时再处理这些依赖。


def format_button_preview(buttons: List[List[dict]]) -> str:
    lines = ["当前按钮预览：", ""]
    idx = 1

    for row in buttons or []:
        if not isinstance(row, list):
            continue
        for btn in row:
            if not isinstance(btn, dict):
                continue

            text = str(btn.get("text") or "").strip()
            reply = str(btn.get("reply") or "").strip()

            if text:
                lines.append(f"{idx}. {text}")
                if reply:
                    lines.append(f"   回复：{reply}")
                idx += 1

    if idx == 1:
        lines.append("暂无按钮")

    return "\n".join(lines)


async def format_all_tenants_text(tenants: List[dict]) -> str:
    if not tenants:
        return "当前暂无租户。"

    lines = ["🏢 <b>所有租户</b>", ""]

    for idx, t in enumerate(tenants, start=1):
        tenant_name = t.get("tenantName") or t.get("tenantId")
        tenant_id = str(t.get("tenantId") or "").strip()

        bots = await _legacy().list_bots_by_tenant_id(tenant_id) if tenant_id else []
        bot_count_text = str(len(bots))

        status = str(t.get("status") or "active")
        if status == "deleted":
            status_text = "🗑 已删除"
        elif t.get("isBlacklisted"):
            status_text = "⛔ 已拉黑"
        else:
            status_text = "✅ 正常"

        lines.append(
            f"{idx}. <b>{escape_html(tenant_name)}</b>\n"
            f"   tenantId: <code>{escape_html(tenant_id)}</code>\n"
            f"   机器人数: <b>{bot_count_text}</b>\n"
            f"   状态: {status_text}"
        )

    return "\n\n".join(lines)


async def format_tenant_summary_text(tenant: dict, bots: Optional[List[dict]] = None) -> str:
    tenant_name = tenant.get("tenantName") or tenant.get("tenantId")
    tenant_id = str(tenant.get("tenantId") or "").strip()

    if bots is None:
        bots = await _legacy().list_bots_by_tenant_id(tenant_id) if tenant_id else []
    bot_count_text = str(len(bots))

    status = str(tenant.get("status") or "active")
    if status == "deleted":
        status_text = "🗑 已删除"
    elif tenant.get("isBlacklisted"):
        status_text = "⛔ 已拉黑"
    else:
        status_text = "✅ 正常"

    category = str(tenant.get("category") or "other")
    category_label_map = {
        "local": "招商(本)",
        "external": "招商(外)",
        "other": "其他",
        "blacklisted": "已拉黑",
    }
    category_label = category_label_map.get(category, "其他")

    creator_username = str(tenant.get("creatorUsername") or "").strip().lstrip("@")
    admin_chat_id = int(tenant.get("adminChatId") or 0)

    tenant_link = ""
    if creator_username:
        tenant_link = f"https://t.me/{creator_username}"
    elif admin_chat_id:
        tenant_link = f"tg://user?id={admin_chat_id}"

    tenant_title = (
        f'<a href="{tenant_link}"><b>{escape_html(tenant_name)}</b></a>'
        if tenant_link else
        f"<b>{escape_html(tenant_name)}</b>"
    )

    started_user_count = int(tenant.get("startedUserCount") or 0)

    return (
        f"🏢 租户：{tenant_title}\n"
        f"🤖 机器人数：<b>{bot_count_text}</b>\n"
        f"📌 状态：<b>{status_text}</b>\n"
        f"👥 启动用户数：<b>{started_user_count}</b>\n"
        f"📂 分类：<b>{category_label}</b>"
    )


def format_started_users_text(owner: dict, users: List[dict]) -> str:
    if not users:
        return "暂无启动记录"

    lines = []
    grouped = OrderedDict()

    for u in users[:100]:
        bot_username = str(u.get("botUsername") or "").strip()
        bot_show = f"@{bot_username}" if bot_username else "@unknownbot"

        if bot_show not in grouped:
            grouped[bot_show] = []
        grouped[bot_show].append(u)

    idx = 1
    for bot_show, bot_users in grouped.items():
        lines.append(f"<b>{escape_html(bot_show)}</b>")

        for u in bot_users:
            username = str(u.get("username") or "").strip()
            first_name = str(u.get("firstName") or "").strip()
            last_name = str(u.get("lastName") or "").strip()
            source = str(u.get("source") or "direct")
            user_id = int(u.get("userId") or 0)
            started_date = format_date_ymd(u.get("startedAt"))

            display_name = (
                f"@{username}"
                if username else
                (" ".join([x for x in [first_name, last_name] if x]).strip() or f"UID:{user_id}")
            )

            lines.append(
                f"{started_date} {idx}. "
                f'<a href="tg://user?id={user_id}">{escape_html(display_name)}</a> '
                f'| UID:<code>{user_id}</code> | 来源:<code>{escape_html(source)}</code>'
            )
            idx += 1

        lines.append("")

    if len(users) > 100:
        lines.append(f"仅显示前 100 条记录，共 {len(users)} 条")

    return "\n".join(lines).strip()


def format_tenant_category_text(tenant: dict) -> str:
    return "点击下方按钮更改分类。"


def build_apply_summary(apply: dict) -> str:
    if apply.get("type") == "update":
        patch_text = "\n".join(
            f"- {k}: {str(v)}" for k, v in (apply.get("updatePatch") or {}).items()
        )
        return (
            "🛠 <b>机器人修改申请</b>\n"
            "━━━━━━━━━━\n"
            f"🆔 申请ID：<code>{escape_html(apply.get('applyId', ''))}</code>\n"
            f"👤 申请人：{escape_html(apply.get('applicantDisplayName', '-') or '-')}\n"
            f"💬 Chat ID：<code>{apply.get('applicantChatId', '-')}</code>\n"
            f"🏢 tenantId：<code>{escape_html(apply.get('tenantId', '-') or '-')}</code>\n"
            f"🤖 botId：<code>{escape_html(apply.get('botId', '-') or '-')}</code>\n"
            f"📝 修改字段：<b>{escape_html(apply.get('updateFieldLabel', '-') or '-')}</b>\n"
            f"📦 修改内容：\n<pre>{escape_html(patch_text or '-')}</pre>\n"
            f"📌 状态：<b>{escape_html(apply.get('status', 'pending'))}</b>"
        )

    return (
        "📝 <b>新机器人接入申请</b>\n"
        "━━━━━━━━━━\n"
        f"🆔 申请ID：<code>{escape_html(apply.get('applyId', ''))}</code>\n"
        f"👤 申请人：{escape_html(apply.get('applicantDisplayName', '-') or '-')}\n"
        f"💬 Chat ID：<code>{apply.get('applicantChatId', '-')}</code>\n"
        f"🏢 tenantId：<code>{escape_html(apply.get('tenantId', '-') or '-')}</code>\n"
        f"🏢 租户名称：<b>{escape_html(apply.get('tenantName', '-') or '-')}</b>\n"
        f"🤖 机器人用户名：<b>{escape_html('@' + (((apply.get('botInfo') or {}).get('username')) or ''))}</b>\n"
        f"🤖 Bot Token：<code>{escape_html(mask_bot_token(apply.get('botToken', '') or ''))}</code>\n"
        f"🔗 详情链接：{escape_html(apply.get('detailUrl', '-') or '-')}\n"
        f"📌 状态：<b>{escape_html(apply.get('status', 'pending'))}</b>"
    )


def build_creator_signature(bot: dict) -> str:
    return "\n\n该Bot由 @SXX77bot 创建"


def build_final_welcome_text(bot: dict, ad_config: Optional[dict] = None) -> str:
    base = str(bot.get("welcomeText") or DEFAULT_WELCOME_TEXT).rstrip()
    text = base + build_creator_signature(bot)

    items = (ad_config or {}).get("items") or []
    ad_lines = []

    for item in items:
        ad_text = str(item.get("text") or "").strip()
        ad_url = str(item.get("url") or "").strip()

        if ad_text and ad_url:
            ad_lines.append(
                f'<a href="{html.escape(ad_url, quote=True)}">{escape_html(ad_text)}</a>'
            )

    if ad_lines:
        text += "\n\n广告：\n" + "\n".join(ad_lines)

    return text
