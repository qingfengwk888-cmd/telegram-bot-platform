from app.telegram.api import tg


async def try_handle_tenant_help_message(
    *,
    platform_bot_token: str,
    chat_id: int,
    text: str,
) -> bool:
    if text != "💬 帮助中心":
        return False

    await tg(platform_bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": (
            "帮助中心\n\n"
            "一、如何创建机器人\n\n"
            "要创建机器人，您应遵循以下两个步骤：\n\n"
            "1. 打开 @BotFather 并创建一个新的机器人。\n\n"
            "2. 创建完成后，您会得到一个令牌（例如：12345:6789ABCDEF），"
            "只需将该令牌转发给我，或直接复制粘贴发送给我即可。\n\n"
            "3. 查看视频教程 >> <a href=\"https://t.me/SXX777bot/2\">查看</a>\n\n"
            "警告：\n"
            "请不要连接其他机器人服务，也不要使用已经接入过其他服务的机器人，"
            "否则可能会导致功能异常。\n\n"
            "二、如何拉黑 / 解黑用户\n\n"
            "1. 直接回复对方的启动信息，或对方发送的消息内容。\n\n"
            "2. 回复“拉黑”即可拉黑该用户，回复“解黑”即可解除拉黑。\n\n"
            "三、如何查看客户来源\n\n"
            "1. 当客户通过深链接启动您的机器人时，系统会自动提取并显示来源信息。\n\n"
            "2. 示例：\n"
            "https://t.me/你的机器人用户名?start=jisou\n\n"
            "如果客户通过这个链接启动您的机器人，来源将显示为：jisou\n\n"
            "3. 等号后面的来源参数可以自由设置。\n\n"
            "注意：\n"
            "来源参数不能使用中文，建议仅使用英文、数字、下划线（_）或短横线（-），这样更稳定。\n\n"
            "四、为什么机器人无法接入\n\n"
            "1. 请确认您发送的是 @BotFather 提供的完整 Bot Token。\n\n"
            "2. 请确认该机器人没有接入过其他机器人平台或第三方服务。\n\n"
            "3. 如果提示机器人已存在，说明该机器人已经接入过，无法重复接入。"
        ),
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    })
    return True
