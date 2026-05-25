import re
from typing import Optional

from app.utils.helpers import sanitize_tenant_id


async def extract_bot_id_from_callback_data(data: str) -> Optional[str]:
    if data in {"bot_noop", "bot_manage:back_to_list", "bot_blacklist_back"}:
        return ""
    data = str(data or "").strip()

    patterns = [
        r"^bot_select:[^:]+:(.+)$",
        r"^bot_manage:(.+)$",
        r"^bot_remove:(.+)$",
        r"^bot_remove_confirm:(.+)$",
        r"^button_manage:[^:]+:(.+)$",
        r"^button_delete:(.+):\d+$",
    ]

    for p in patterns:
        m = re.match(p, data)
        if m:
            return sanitize_tenant_id(m.group(1))

    return None


def parse_start_payload(text: str = "") -> str:
    text = (text or "").strip()
    m = re.match(r"^/start(?:\s+(.+))?$", text)
    if not m:
        return ""
    return (m.group(1) or "").strip()


def should_handle_as_admin_message(msg: dict) -> bool:
    text = str(msg.get("text") or "").strip()
    replied = msg.get("reply_to_message")

    if replied:
        return True

    if text in {"拉黑", "解黑"}:
        return True

    # 管理员直接给租户机器人发普通消息时，也进入管理员回复逻辑；
    # 是否存在当前锁定用户，由 admin_message_service 再判断。
    if text and not text.startswith("/"):
        return True

    if any(msg.get(k) for k in ["photo", "video", "document", "voice", "audio", "sticker", "animation"]):
        return True

    return False
