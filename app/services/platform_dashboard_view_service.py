from typing import List

from app.services.tenant_service import get_tenant_index, list_bots_by_tenant_id, load_tenant
from app.telegram.formatters import escape_html
from app.utils.helpers import format_date_ymd


def format_simple_tenant_list_text(title: str, tenants: List[dict]) -> str:
    lines = [title, ""]

    if not tenants:
        lines.append("当前暂无租户。")
        return "\n".join(lines)

    lines.append(f"共 {len(tenants)} 个租户")
    lines.append("请选择一个租户查看详情：")
    return "\n".join(lines)


async def build_platform_dashboard_text() -> str:
    tenant_ids = await get_tenant_index()

    deleted_tenants = 0
    total_tenants = 0
    active_tenants = 0
    blacklisted_tenants = 0

    category_counts = {
        "local": 0,
        "external": 0,
        "other": 0,
        "blacklisted": 0,
    }

    total_started_users = 0
    today_started_users = 0
    recent_tenants = []


    for tenant_id in tenant_ids:
        tenant = await load_tenant(tenant_id)
        if not tenant:
            continue

        status = str(tenant.get("status") or "active")
        if status == "deleted":
            deleted_tenants += 1
            total_tenants += 1
            continue

        total_tenants += 1

        if tenant.get("isBlacklisted"):
            blacklisted_tenants += 1
            category_counts["blacklisted"] += 1
        else:
            active_tenants += 1

            category = str(tenant.get("category") or "other")
            if category not in {"local", "external", "other"}:
                category = "other"
            category_counts[category] += 1

        bots = await list_bots_by_tenant_id(tenant_id)

        total_started_users += int(tenant.get("startedUserCount") or 0)
        today_started_users += int(tenant.get("todayStartedUserCount") or 0)


        recent_bot_username = ""
        if bots:
            latest_bot = max(
                bots,
                key=lambda x: int(x.get("createdAt") or 0)
            )
            recent_bot_username = str(((latest_bot.get("botInfo") or {}).get("username") or "")).strip()

        latest_bot_created_at = 0
        if bots:
            latest_bot_created_at = int(latest_bot.get("createdAt") or 0)

        recent_tenants.append({
            "tenantId": tenant_id,
            "tenantName": tenant.get("tenantName") or tenant_id,
            "botUsername": recent_bot_username,
            "creatorUsername": str(tenant.get("creatorUsername") or "").strip().lstrip("@"),
            "adminChatId": int(tenant.get("adminChatId") or 0),
            "createdAt": latest_bot_created_at or int(tenant.get("createdAt") or 0),
        })

    recent_tenants.sort(key=lambda x: x["createdAt"], reverse=True)

    lines = [
        "📊 <b>平台数据概览</b>",
        "",
        f"🏢 总租户数：<b>{total_tenants}</b>",
        f"✅ 正常租户：<b>{active_tenants}</b>",
        f"⛔ 拉黑租户：<b>{blacklisted_tenants}</b>",
        f"🗑 已删除租户：<b>{deleted_tenants}</b>",
        "",
        f"👥 总启动用户数：<b>{total_started_users}</b>",
        f"🆕 今日新增启动用户：<b>{today_started_users}</b>",
        "",
        "📂 分类统计：",
        f"• 招商(本)：<b>{category_counts['local']}</b>",
        f"• 招商(外)：<b>{category_counts['external']}</b>",
        f"• 其他：<b>{category_counts['other']}</b>",
        f"• 已拉黑：<b>{category_counts['blacklisted']}</b>",
        "",
        "🕘 最近接入租户：",
    ]

    if recent_tenants:
        for idx, item in enumerate(recent_tenants[:5], start=1):
            tenant_name = str(item["tenantName"]).strip()
            bot_username = str(item["botUsername"]).strip()
            creator_username = str(item.get("creatorUsername") or "").strip().lstrip("@")
            admin_chat_id = int(item.get("adminChatId") or 0)
            created_date = format_date_ymd(item["createdAt"])

            tenant_link = ""
            if creator_username:
                tenant_link = f"https://t.me/{creator_username}"
            elif admin_chat_id:
                tenant_link = f"tg://user?id={admin_chat_id}"

            bot_link = f"https://t.me/{bot_username}" if bot_username else ""

            tenant_title = (
                f'<a href="{tenant_link}"><b>{escape_html(tenant_name)}</b></a>'
                if tenant_link else
                f"<b>{escape_html(tenant_name)}</b>"
            )

            bot_title = (
                f'<a href="{bot_link}">@{escape_html(bot_username)}</a>'
                if bot_link else
                "未获取"
            )

            lines.append(
                f"{idx}. {tenant_title} | {bot_title} | {created_date}"
            )
    else:
        lines.append("暂无租户数据")

    return "\n".join(lines)
