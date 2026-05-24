from app.telegram.api import tg


async def try_handle_platform_admin_help_message(
    *,
    platform_bot_token: str,
    chat_id: int,
) -> bool:
    await tg(platform_bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": (
            "管理员功能：\n"
            "1. 🏢 所有租户\n"
            "2. 👥 租户启动用户\n"
            "3. 📣 单租户群发\n"
            "4. 🌐 全部群发\n\n"
            "也可以直接使用命令：\n"
            "/users tenantId\n"
            "/broadcast tenantId 内容\n"
            "/broadcast_all 内容"
        ),
    })
    return True
