from typing import List, Dict

from app.config import PLATFORM_ADMIN_CHAT_ID, PLATFORM_SECONDARY_ADMIN_CHAT_IDS
from app.utils.helpers import escape_html


def is_primary_platform_admin(chat_id: int) -> bool:
    return int(chat_id) == int(PLATFORM_ADMIN_CHAT_ID)


def is_secondary_platform_admin(chat_id: int) -> bool:
    return int(chat_id) in PLATFORM_SECONDARY_ADMIN_CHAT_IDS


def build_bot_pick_buttons(bots: List[dict], action: str) -> dict:
    items = []

    for b in bots:
        bot_id = str(b.get("botId") or "").strip()
        bot_username = str(((b.get("botInfo") or {}).get("username") or "")).strip()
        tenant_name = str(b.get("tenantName") or bot_id).strip()

        if not bot_id:
            continue

        show_name = f"@{bot_username}" if bot_username else tenant_name

        items.append({
            "text": show_name,
            "callback_data": f"bot_select:{action}:{bot_id}"
        })

    if not items:
        return {
            "inline_keyboard": [[
                {"text": "暂无可选机器人", "callback_data": "bot_noop"}
            ]]
        }

    rows = []
    for i in range(0, len(items), 2):
        rows.append(items[i:i + 2])

    return {"inline_keyboard": rows}


def build_my_bots_action_buttons(bots: List[dict]) -> dict:
    rows = []

    for b in bots:
        bot_id = str(b.get("botId") or "").strip()
        bot_username = str(((b.get("botInfo") or {}).get("username") or "")).strip()
        tenant_name = str(b.get("tenantName") or bot_id).strip()

        if not bot_id:
            continue

        show_name = f"@{bot_username}" if bot_username else tenant_name

        rows.append([
            {
                "text": f"💬 {show_name}",
                "callback_data": f"bot_select:welcome:{bot_id}"
            },
            {
                "text": f"🔘 {show_name}",
                "callback_data": f"bot_select:buttons:{bot_id}"
            }
        ])

    if not rows:
        rows = [[{"text": "暂无机器人", "callback_data": "bot_noop"}]]

    return {"inline_keyboard": rows}


def build_button_flow_action_buttons() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "➕ 继续添加", "callback_data": "button_flow:add_more"},
                {"text": "✅ 完成提交", "callback_data": "button_flow:finish"},
            ],
            [
                {"text": "❌ 取消", "callback_data": "button_flow:cancel"},
            ]
        ]
    }


def build_global_broadcast_confirm_buttons() -> dict:
    return {
        "inline_keyboard": [[
            {"text": "✅ 确认", "callback_data": "platform_global_broadcast_confirm"},
            {"text": "❌ 取消", "callback_data": "platform_global_broadcast_cancel"},
        ]]
    }


def build_global_broadcast_target_buttons() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "🏢 全部租户", "callback_data": "platform_global_broadcast_target:tenants"},
                {"text": "👥 全部用户", "callback_data": "platform_global_broadcast_target:tenant_users"},
            ],
            [
                {"text": "🌍 所有人", "callback_data": "platform_global_broadcast_target:all_people"},
            ],
            [
                {"text": "❌ 取消", "callback_data": "platform_global_broadcast_target:cancel"},
            ]
        ]
    }


def build_modify_confirm_buttons() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "✅ 确认提交", "callback_data": "modify_submit:confirm"},
                {"text": "✏️ 重新填写", "callback_data": "modify_submit:retry"},
            ],
            [
                {"text": "❌ 取消", "callback_data": "modify_submit:cancel"},
            ]
        ]
    }


def build_my_bots_entry_buttons(bots: List[dict]) -> dict:
    items = []

    for b in bots:
        bot_id = str(b.get("botId") or "").strip()
        bot_username = str(((b.get("botInfo") or {}).get("username") or "")).strip()
        tenant_name = str(b.get("tenantName") or bot_id).strip()

        if not bot_id:
            continue

        show_name = f"@{bot_username}" if bot_username else tenant_name

        items.append({
            "text": show_name,
            "callback_data": f"bot_manage:{bot_id}"
        })

    if not items:
        return {
            "inline_keyboard": [[{"text": "暂无机器人", "callback_data": "bot_noop"}]]
        }

    rows = []
    for i in range(0, len(items), 2):
        rows.append(items[i:i + 2])

    return {"inline_keyboard": rows}


def build_single_bot_action_buttons(bot_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "💬 设置欢迎语", "callback_data": f"bot_select:welcome:{bot_id}"},
                {"text": "🔘 设置按钮", "callback_data": f"bot_select:buttons:{bot_id}"},
            ],
            [
                {"text": "🚫 查看黑名单", "callback_data": f"bot_select:blacklist:{bot_id}"},
                {"text": "📣 群发消息", "callback_data": f"bot_select:broadcast:{bot_id}"},
            ],
            [
                {"text": "🗑 移除机器人", "callback_data": f"bot_remove:{bot_id}"},
                {"text": "⬅️ 返回机器人列表", "callback_data": "bot_manage:back_to_list"},
            ],
        ]
    }


def build_button_manage_menu_buttons(bot_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "➕ 增加", "callback_data": f"button_manage:add:{bot_id}"},
                {"text": "🗑 删除", "callback_data": f"button_manage:delete:{bot_id}"},
            ],
            [
                {"text": "⬅️ 返回", "callback_data": f"button_manage:back:{bot_id}"},
            ]
        ]
    }


def build_button_delete_pick_buttons(bot_id: str, buttons: List[List[dict]]) -> dict:
    rows = []
    flat_buttons = []

    for row in buttons or []:
        if not isinstance(row, list):
            continue
        for btn in row:
            if not isinstance(btn, dict):
                continue
            text = str(btn.get("text") or "").strip()
            if text:
                flat_buttons.append(text)

    for idx, text in enumerate(flat_buttons):
        rows.append([{
            "text": f"🗑 删除：{text}",
            "callback_data": f"button_delete:{bot_id}:{idx}"
        }])

    rows.append([{
        "text": "⬅️ 返回",
        "callback_data": f"button_manage:menu:{bot_id}"
    }])

    return {"inline_keyboard": rows}


def build_button_reply_map(buttons: List[List[dict]]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for row in buttons or []:
        if not isinstance(row, list):
            continue
        for btn in row:
            if not isinstance(btn, dict):
                continue
            text = str(btn.get("text") or "").strip()
            reply = str(btn.get("reply") or "").strip()
            if text and reply:
                result[text] = reply
    return result


def build_profile_buttons(
    user_id: int,
    username: str = "",
    display_name: str = "",
    tenant_id: str = "",
    bot_id: str = "",
) -> list:
    buttons = []

    if username:
        buttons.append({
            "text": f"👤 @{username}",
            "url": f"https://t.me/{username}"
        })
    elif bot_id:
        buttons.append({
            "text": f"👤 UID:{user_id}",
            "callback_data": f"bot_user_profile:{bot_id}:{user_id}"
        })
    else:
        buttons.append({
            "text": f"👤 UID:{user_id}",
            "callback_data": "noop"
        })

    return [buttons]


def flatten_welcome_buttons(buttons: List[List[dict]]) -> List[dict]:
    result = []
    for row in buttons or []:
        if not isinstance(row, list):
            continue
        for btn in row:
            if isinstance(btn, dict):
                result.append(btn)
    return result


def rebuild_button_rows(flat_buttons: List[dict]) -> List[List[dict]]:
    rows = []
    clean = []

    for btn in flat_buttons or []:
        if not isinstance(btn, dict):
            continue
        text = str(btn.get("text") or "").strip()
        reply = str(btn.get("reply") or "").strip()
        if text:
            clean.append({
                "text": text,
                "reply": reply,
            })

    for i in range(0, len(clean), 2):
        rows.append(clean[i:i + 2])

    return rows


def build_remove_confirm_buttons(bot_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "✅ 确认移除", "callback_data": f"bot_remove_confirm:{bot_id}"},
                {"text": "❌ 取消", "callback_data": "bot_remove_cancel"},
            ]
        ]
    }


def build_platform_reply_keyboard_for_admin(chat_id: int) -> dict:
    rows = [
        [{"text": "📊 数据概览"}, {"text": "🏢 所有租户"}],
    ]

    if is_primary_platform_admin(chat_id):
        rows.append([{"text": "🌐 全部群发"}, {"text": "📢 广告设置"}])

    return {
        "keyboard": rows,
        "resize_keyboard": True,
        "is_persistent": True,
    }


def build_bot_reply_keyboard(bot: dict) -> dict:
    buttons = bot.get("welcomeButtons") or []
    flat_buttons = []

    # 先把所有按钮拍平成一维
    for row in buttons:
        if not isinstance(row, list):
            continue

        for btn in row:
            if not isinstance(btn, dict):
                continue

            text = str(btn.get("text") or "").strip()
            if text:
                flat_buttons.append({"text": text})

    # 没有按钮就移除键盘
    if not flat_buttons:
        return {"remove_keyboard": True}

    # 每两个按钮组成一行
    rows = []
    for i in range(0, len(flat_buttons), 2):
        rows.append(flat_buttons[i:i + 2])

    return {
        "keyboard": rows,
        "resize_keyboard": True,
        "is_persistent": True,
    }


def build_platform_ad_menu_buttons() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "➕ 新增广告", "callback_data": "platform_ad_menu:add"},
                {"text": "✏️ 修改广告", "callback_data": "platform_ad_menu:edit"},
            ],
            [
                {"text": "🗑 删除广告", "callback_data": "platform_ad_menu:delete"},
            ]
        ]
    }


def build_platform_ad_pick_buttons(items: List[dict], action: str) -> dict:
    rows = []

    for item in items:
        ad_id = str(item.get("adId") or "").strip()
        ad_text = str(item.get("text") or "").strip()

        if not ad_id:
            continue

        show_text = ad_text[:20] if ad_text else ad_id
        rows.append([{
            "text": show_text,
            "callback_data": f"platform_ad_pick:{action}:{ad_id}"
        }])

    if not rows:
        rows = [[{"text": "暂无广告", "callback_data": "noop"}]]

    return {"inline_keyboard": rows}


def build_platform_reply_keyboard_for_tenant() -> dict:
    return {
        "keyboard": [
            [{"text": "📝 添加机器人"}, {"text": "📁 我的机器人"}],
            [{"text": "💬 帮助中心"}, {"text": "🇨🇳 切换中文包"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def build_admin_tenant_pick_buttons(tenants: List[dict]) -> dict:
    rows = []

    for t in tenants:
        tenant_id = str(t.get("tenantId") or "").strip()
        tenant_name = str(t.get("tenantName") or tenant_id).strip()

        if not tenant_id:
            continue

        rows.append([{
            "text": f"{tenant_name} | {tenant_id}",
            "callback_data": f"admin_tenant:view:{tenant_id}"
        }])

    if not rows:
        rows = [[{"text": "暂无可选租户", "callback_data": "noop"}]]

    return {"inline_keyboard": rows}


def build_admin_tenant_root_menu_buttons() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "📈 按流量", "callback_data": "admin_tenant_menu:traffic"},
                {"text": "📂 按分类", "callback_data": "admin_tenant_menu:category"},
            ]
        ]
    }


def build_admin_tenant_traffic_sort_buttons() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "⬇️ 从高到低", "callback_data": "admin_tenant_sort:desc"},
                {"text": "⬆️ 从低到高", "callback_data": "admin_tenant_sort:asc"},
            ],
            [
                {"text": "⬅️ 返回上级", "callback_data": "admin_tenant_back:root"},
            ]
        ]
    }


def build_admin_tenant_category_buttons() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "招商(本)", "callback_data": "admin_tenant_filter:category:local"},
                {"text": "招商(外)", "callback_data": "admin_tenant_filter:category:external"},
            ],
            [
                {"text": "其他", "callback_data": "admin_tenant_filter:category:other"},
                {"text": "已拉黑", "callback_data": "admin_tenant_filter:category:blacklisted"},
            ],
            [
                {"text": "⬅️ 返回上级", "callback_data": "admin_tenant_back:root"},
            ]
        ]
    }


def build_admin_tenant_pick_buttons_with_back(tenants: List[dict], back_to: str) -> dict:
    rows = []

    for t in tenants:
        tenant_id = str(t.get("tenantId") or "").strip()
        tenant_name = str(t.get("tenantName") or tenant_id).strip()

        if not tenant_id:
            continue

        rows.append([{
            "text": f"{tenant_name} | {tenant_id}",
            "callback_data": f"admin_tenant:view:{tenant_id}"
        }])

    if not rows:
        rows = [[{"text": "暂无可选租户", "callback_data": "noop"}]]

    rows.append([{"text": "⬅️ 返回上级", "callback_data": back_to}])
    return {"inline_keyboard": rows}


def build_tenant_category_buttons(tenant_id: str) -> list:
    return [
        [
            {"text": "招商(本)", "callback_data": f"tenant_category:local:{tenant_id}"},
            {"text": "招商(外)", "callback_data": f"tenant_category:external:{tenant_id}"},
            {"text": "其他", "callback_data": f"tenant_category:other:{tenant_id}"},
        ],
        [
            {"text": "拉黑", "callback_data": f"tenant_black_toggle:black:{tenant_id}"},
            {"text": "解黑", "callback_data": f"tenant_black_toggle:unblack:{tenant_id}"},
        ]
    ]


def build_tenant_detail_category_buttons(tenant_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "招商(本)", "callback_data": f"tenant_category:local:{tenant_id}"},
                {"text": "招商(外)", "callback_data": f"tenant_category:external:{tenant_id}"},
                {"text": "其他", "callback_data": f"tenant_category:other:{tenant_id}"},
            ],
            [
                {"text": "拉黑", "callback_data": f"tenant_black_toggle:black:{tenant_id}"},
                {"text": "解黑", "callback_data": f"tenant_black_toggle:unblack:{tenant_id}"},
            ]
        ]
    }


def build_tenant_detail_action_buttons(tenant_id: str, chat_id: int) -> dict:
    rows = [
        [
            {"text": "招商(本)", "callback_data": f"tenant_category:local:{tenant_id}"},
            {"text": "招商(外)", "callback_data": f"tenant_category:external:{tenant_id}"},
            {"text": "其他", "callback_data": f"tenant_category:other:{tenant_id}"},
        ],
        [
            {"text": "拉黑", "callback_data": f"tenant_black_toggle:black:{tenant_id}"},
            {"text": "解黑", "callback_data": f"tenant_black_toggle:unblack:{tenant_id}"},
        ],
    ]

    if not is_secondary_platform_admin(chat_id):
        rows.append([
            {"text": "📣 群发消息", "callback_data": f"admin_tenant_broadcast:{tenant_id}"},
        ])

    return {"inline_keyboard": rows}


def build_new_tenant_notice_buttons(tenant: dict) -> dict:
    tenant_id = str(tenant.get("tenantId") or "").strip()
    category = str(tenant.get("category") or "other")
    is_blacklisted = bool(tenant.get("isBlacklisted"))

    return {
        "inline_keyboard": [
            [
                {
                    "text": "✅ 招商(本)" if category == "local" else "招商(本)",
                    "callback_data": f"tenant_category:local:{tenant_id}",
                },
                {
                    "text": "✅ 招商(外)" if category == "external" else "招商(外)",
                    "callback_data": f"tenant_category:external:{tenant_id}",
                },
                {
                    "text": "✅ 其他" if category == "other" else "其他",
                    "callback_data": f"tenant_category:other:{tenant_id}",
                },
            ],
            [
                {
                    "text": "✅ 已拉黑" if is_blacklisted else "拉黑",
                    "callback_data": f"tenant_black_toggle:black:{tenant_id}",
                },
                {
                    "text": "解黑" if is_blacklisted else "✅ 已解黑",
                    "callback_data": f"tenant_black_toggle:unblack:{tenant_id}",
                },
            ]
        ]
    }


def build_apply_approve_buttons(apply_id: str) -> List[List[dict]]:
    return [[
        {"text": "✅ 同意", "callback_data": f"apply:approve:{apply_id}"},
        {"text": "❌ 拒绝", "callback_data": f"apply:reject:{apply_id}"},
    ]]


def build_welcome_buttons(bot: dict) -> List[List[dict]]:
    buttons = bot.get("welcomeButtons") or []
    keyboard: List[List[dict]] = []

    if isinstance(buttons, list):
        for row in buttons:
            if not isinstance(row, list):
                continue

            row_buttons = []
            for btn in row:
                if not isinstance(btn, dict):
                    continue

                text = str(btn.get("text") or "").strip()
                url = str(btn.get("url") or "").strip()
                callback_data = str(btn.get("callback_data") or "").strip()

                if text and url:
                    row_buttons.append({"text": text, "url": url})
                elif text and callback_data:
                    row_buttons.append({"text": text, "callback_data": callback_data})

            if row_buttons:
                keyboard.append(row_buttons)

    return keyboard
