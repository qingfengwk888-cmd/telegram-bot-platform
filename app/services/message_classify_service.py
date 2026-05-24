from app.services.rate_limit_service import normalize_rate_action
from app.services.user_service import find_bot_button_reply
from app.services.user_service import find_bot_button_reply


def is_plain_user_text_message(text: str) -> bool:
    text = str(text or "").strip()
    if not text:
        return False

    # 命令不是普通消息
    if text.startswith("/"):
        return False

    # 这里如果你后续还有菜单关键词，也可以继续排除
    # 比如某些固定功能入口词：
    special_actions = {
        "帮助",
        "菜单",
        "开始",
    }
    if text in special_actions:
        return False

    return True


def classify_message_action(text: str, bot: dict) -> str:
    text = str(text or "").strip()

    if not text:
        return "empty"

    if text.startswith("/"):
        return f"command:{text.split()[0].lower()}"

    reply = find_bot_button_reply(bot, text)
    if reply:
        return f"button_reply:{normalize_rate_action(text)}"

    special_actions = {
        "帮助": "action:help",
        "菜单": "action:menu",
        "开始": "action:start",
    }
    if text in special_actions:
        return special_actions[text]

    return "plain_text"


def classify_platform_action(text: str) -> str:
    text = str(text or "").strip()
    if not text:
        return "empty"

    if text.startswith("/"):
        return f"platform_command:{text.split()[0].lower()}"

    special_actions = {
        "📝 添加机器人": "platform_action:apply",
        "📁 我的机器人": "platform_action:my_bots",
        "💬 帮助中心": "platform_action:help",
        "🇨🇳 切换中文包": "platform_action:switch_lang",
    }
    return special_actions.get(text, "platform_plain_text")
