import time
import uuid
from typing import Optional, Dict, Any, List

from fastapi import Request

from app.config import APPLY_RECORD_TTL_SECONDS, APPLY_SESSION_TTL_SECONDS
from app.storage.repository import redis_get_json_db, redis_set_json_db, kv_delete_db
from app.storage.redis_compat import redis_client
from app.utils.helpers import escape_html, now_ms, sanitize_tenant_id, build_bot_id_from_bot_username
from app.telegram.api import tg, telegram_raw
from app.services.bot_service import load_bot, save_bot
from app.services.bot_onboarding_service import create_bot_from_payload


# 兼容 legacy_app 旧函数名
redis_get_json = redis_get_json_db
redis_set_json = redis_set_json_db


def generate_apply_id() -> str:
    return f"apply_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"


def apply_key(apply_id: str) -> str:
    return f"apply:{apply_id}"


def apply_index_key() -> str:
    return "apply:index"


def apply_session_key(user_id: int) -> str:
    return f"apply:session:{user_id}"


async def load_apply(apply_id: str) -> Optional[dict]:
    return await redis_get_json(apply_key(apply_id))


async def save_apply(apply: dict) -> None:
    key = apply_key(apply["applyId"])
    await redis_set_json(key, apply, APPLY_RECORD_TTL_SECONDS)
    await redis_client.lrem(apply_index_key(), 0, apply["applyId"])
    await redis_client.lpush(apply_index_key(), apply["applyId"])


async def get_apply_index(limit: int = 100) -> List[str]:
    return await redis_client.lrange(apply_index_key(), 0, max(limit - 1, 0))


async def load_apply_session(user_id: int) -> Optional[dict]:
    return await redis_get_json(apply_session_key(user_id))


async def save_apply_session(user_id: int, session: dict) -> None:
    await redis_set_json(apply_session_key(user_id), session, APPLY_SESSION_TTL_SECONDS)


async def clear_apply_session(user_id: int) -> None:
    await redis_client.delete(apply_session_key(user_id))


async def create_bot_from_apply(request: Request, apply: dict) -> dict:
    return await create_bot_from_payload(
        request,
        {
            "tenantId": apply.get("tenantId"),
            "tenantName": apply.get("tenantName"),
            "botToken": apply.get("botToken"),
            "adminChatId": apply.get("applicantChatId"),
            "detailUrl": apply.get("detailUrl") or "",
            "status": "active",
            "creatorUsername": apply.get("creatorUsername") or apply.get("applicantUsername") or "",
            "creatorName": apply.get("creatorName") or apply.get("applicantDisplayName") or "",
            "welcomeButtons": apply.get("welcomeButtons") or [],
        },
    )


async def apply_bot_update(apply: dict) -> dict:
    bot_id = sanitize_tenant_id(apply.get("botId") or "")
    if not bot_id:
        raise ValueError("botId_required")

    bot = await load_bot(bot_id)
    if not bot:
        raise ValueError("bot_not_found")

    if int(bot.get("adminChatId", 0)) != int(apply.get("applicantChatId", 0)):
        raise ValueError("permission_denied")

    patch = apply.get("updatePatch") or {}
    allowed_keys = {
        "welcomeText",
        "welcomeButtons",
        "firstAckText",
        "detailUrl",
        "detailButtonText",
        "creatorUsername",
        "creatorName",
    }

    for key, value in patch.items():
        if key not in allowed_keys:
            raise ValueError(f"field_not_allowed:{key}")

        if key == "welcomeButtons":
            bot[key] = value if isinstance(value, list) else []
        else:
            bot[key] = str(value)

    bot["updatedAt"] = now_ms()
    await save_bot(bot)
    return {"bot": bot}


# ============================================================
# Platform bot flows
# ============================================================
