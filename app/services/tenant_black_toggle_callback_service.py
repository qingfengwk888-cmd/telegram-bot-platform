import re


async def try_handle_tenant_black_toggle_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
    message: dict,
) -> bool:
    from app import legacy_app as legacy

    black_match = re.match(r"^tenant_black_toggle:(black|unblack):(.+)$", data)
    if not black_match:
        return False

    action = black_match.group(1)
    tenant_id = legacy.sanitize_tenant_id(black_match.group(2))

    tenant = await legacy.load_tenant(tenant_id)
    if not tenant:
        await legacy.tg(platform_bot_token, "answerCallbackQuery", {
            "callback_query_id": callback_query["id"],
            "text": "租户不存在或已删除",
            "show_alert": True,
        })
        return True

    should_black = action == "black"

    # 1. 同步 Redis 黑名单
    await legacy.set_platform_tenant_blacklisted(tenant_id, should_black)

    # 2. 同步 tenant 展示字段
    tenant["isBlacklisted"] = should_black
    tenant["updatedAt"] = legacy.now_ms()
    await legacy.save_tenant(tenant)

    # 3. 通知租户管理员
    tenant_admin_chat_id = int(tenant.get("adminChatId") or 0)
    if tenant_admin_chat_id:
        try:
            await legacy.tg(platform_bot_token, "sendMessage", {
                "chat_id": tenant_admin_chat_id,
                "text": (
                    "⛔ 你已被暂停使用。"
                    if should_black else
                    "✅ 你已恢复使用。"
                ),
            })
        except Exception:
            legacy.logger.exception(
                "notify tenant blacklist state failed tenantId=%s",
                tenant_id,
            )

    await legacy.tg(platform_bot_token, "answerCallbackQuery", {
        "callback_query_id": callback_query["id"],
        "text": "已拉黑该租户" if should_black else "已解除拉黑",
    })

    # 4. 如果当前消息还能编辑，就把当前页面一起刷新
    if message.get("chat", {}).get("id") and message.get("message_id"):
        original_text = str(message.get("text") or "")

        if (
            "🟢 有新租户加入" in original_text
            or "🟢 <b>有新租户加入</b>" in original_text
            or "🟢 有新机器人接入" in original_text
            or "🟢 <b>有新机器人接入</b>" in original_text
        ):
            category = str(tenant.get("category") or "other")

            await legacy.tg(platform_bot_token, "editMessageReplyMarkup", {
                "chat_id": message["chat"]["id"],
                "message_id": message["message_id"],
                "reply_markup": {
                    "inline_keyboard": [
                        [
                            {
                                "text": "✅ 招商(本)" if category == "local" else "招商(本)",
                                "callback_data": f"tenant_category:local:{tenant_id}"
                            },
                            {
                                "text": "✅ 招商(外)" if category == "external" else "招商(外)",
                                "callback_data": f"tenant_category:external:{tenant_id}"
                            },
                            {
                                "text": "✅ 其他" if category == "other" else "其他",
                                "callback_data": f"tenant_category:other:{tenant_id}"
                            },
                        ],
                        [
                            {
                                "text": "✅ 已拉黑" if should_black else "拉黑",
                                "callback_data": f"tenant_black_toggle:black:{tenant_id}"
                            },
                            {
                                "text": "解黑" if should_black else "✅ 已解黑",
                                "callback_data": f"tenant_black_toggle:unblack:{tenant_id}"
                            },
                        ]
                    ]
                },
            })
            return True

        users = await legacy.list_started_users_by_tenant_id(tenant_id)

        await legacy.tg(platform_bot_token, "editMessageText", {
            "chat_id": message["chat"]["id"],
            "message_id": message["message_id"],
            "text": (
                await legacy.format_tenant_summary_text(tenant)
                + "\n\n"
                + legacy.format_started_users_text(tenant, users)
                + "\n\n"
                + legacy.format_tenant_category_text(tenant)
            ),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "reply_markup": legacy.build_tenant_detail_action_buttons(tenant_id, from_id),
        })

    return True
