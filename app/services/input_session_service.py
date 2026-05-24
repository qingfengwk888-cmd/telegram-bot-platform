from typing import Optional

from app.services.apply_service import clear_apply_session


def is_input_session(session: Optional[dict]) -> bool:
    if not session:
        return False

    mode = str(session.get("mode") or "")
    step = str(session.get("step") or "")

    if mode == "create" and step == "bot_token":
        return True

    if mode == "modify" and step in {
        "welcome_text_input",
        "button_text_input",
        "button_reply_input",
        "confirm_submit",
    }:
        return True

    if mode == "tenant_broadcast" and step in {
        "broadcast_input",
        "broadcast_confirm",
    }:
        return True

    if mode == "platform_ad_config" and step in {
        "ad_text_input",
        "ad_url_input",
    }:
        return True

    if mode == "admin_tenant_broadcast" and step in {
        "broadcast_input",
        "broadcast_confirm",
    }:
        return True

    if mode == "platform_global_broadcast" and step in {
        "broadcast_input",
        "broadcast_confirm",
    }:
        return True

    return False


async def interrupt_input_session_if_needed(
    user_id: int,
    session: Optional[dict],
    *,
    platform_bot_token: str,
    notify_chat_id: Optional[int] = None,
) -> Optional[dict]:
    if not is_input_session(session):
        return session

    await clear_apply_session(user_id)
    return None


def is_busy_input_session(session: Optional[dict]) -> bool:
    if not session:
        return False

    mode = str(session.get("mode") or "")
    step = str(session.get("step") or "")

    return (
        (mode == "create" and step == "bot_token")
        or (mode == "modify" and step in {
            "welcome_text_input",
            "button_text_input",
            "button_reply_input",
            "button_more_action",
            "modify_confirm",
        })
        or (mode == "tenant_broadcast" and step in {
            "broadcast_input",
            "broadcast_confirm",
        })
        or (mode == "platform_ad_config" and step in {
            "ad_text_input",
            "ad_url_input",
        })
        or (mode == "admin_tenant_broadcast" and step in {
            "broadcast_input",
            "broadcast_confirm",
        })
        or (mode == "platform_global_broadcast" and step in {
            "broadcast_input",
            "broadcast_confirm",
        })
    )
