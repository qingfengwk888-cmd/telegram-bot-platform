import re
from typing import Optional, Dict, Any

from app.config import (
    RATE_LIMIT_SINGLE_SECONDS,
    RATE_LIMIT_BURST_WINDOW_SECONDS,
    RATE_LIMIT_BURST_MAX_TIMES,
    RATE_LIMIT_MUTE_SECONDS,
    RATE_LIMIT_SINGLE_MSG,
    RATE_LIMIT_MUTE_MSG,
    DUPLICATE_UPDATE_TTL_SECONDS,
)
from app.storage.redis_compat import redis_client
from app.utils.helpers import sanitize_tenant_id


def normalize_rate_action(action: str) -> str:
    s = str(action or "").strip().lower()
    return re.sub(r"[^a-z0-9:_-]", "_", s) or "unknown"


def bot_user_rate_action_key(bot_id: str, user_id: int, action: str) -> str:
    return f"b:{bot_id}:rate:action:{int(user_id)}:{action}"


def bot_user_rate_mute_notice_key(bot_id: str, user_id: int) -> str:
    return f"b:{bot_id}:rate:mute_notice:{int(user_id)}"


def bot_user_rate_burst_key(bot_id: str, user_id: int) -> str:
    return f"b:{bot_id}:rate:burst:{int(user_id)}"


def bot_user_rate_mute_key(bot_id: str, user_id: int) -> str:
    return f"b:{bot_id}:rate:mute:{int(user_id)}"


async def is_duplicate_update(scope: str, update_id: Optional[int]) -> bool:
    if update_id is None:
        return False
    key = f"dup:{scope}:{update_id}"
    result = await redis_client.set(key, "1", ex=DUPLICATE_UPDATE_TTL_SECONDS, nx=True)
    return result is None


async def get_bot_user_rate_limit_status(
    bot_id: str,
    user_id: int,
    action: str,
) -> Dict[str, Any]:
    bot_id = sanitize_tenant_id(bot_id)
    user_id = int(user_id)
    action = normalize_rate_action(action)

    mute_key = bot_user_rate_mute_key(bot_id, user_id)
    mute_notice_key = bot_user_rate_mute_notice_key(bot_id, user_id)
    action_key = bot_user_rate_action_key(bot_id, user_id, action)
    burst_key = bot_user_rate_burst_key(bot_id, user_id)

    # 1) 已在禁言中：只提示一次，后续静默拦截
    mute_ttl = await redis_client.ttl(mute_key)
    if mute_ttl and mute_ttl > 0:
        notice_sent = await redis_client.get(mute_notice_key)
        if notice_sent:
            return {
                "blocked": True,
                "reason": "muted",
                "message": "",
                "retry_after": mute_ttl,
            }

        await redis_client.set(
            mute_notice_key,
            "1",
            ex=max(int(mute_ttl), 1),
        )
        return {
            "blocked": True,
            "reason": "muted",
            "message": RATE_LIMIT_MUTE_MSG,
            "retry_after": mute_ttl,
        }

    # 2) 先累计 20 秒内总触发次数
    burst_count = await redis_client.incr(burst_key)
    if burst_count == 1:
        await redis_client.expire(burst_key, RATE_LIMIT_BURST_WINDOW_SECONDS)

    if burst_count > RATE_LIMIT_BURST_MAX_TIMES:
        await redis_client.set(
            mute_key,
            "1",
            ex=RATE_LIMIT_MUTE_SECONDS,
        )
        await redis_client.set(
            mute_notice_key,
            "1",
            ex=RATE_LIMIT_MUTE_SECONDS,
        )
        return {
            "blocked": True,
            "reason": "burst_too_many",
            "message": RATE_LIMIT_MUTE_MSG,
            "retry_after": RATE_LIMIT_MUTE_SECONDS,
        }

    # 3) 再做 3 秒同功能限流
    single_ok = await redis_client.set(
        action_key,
        "1",
        ex=RATE_LIMIT_SINGLE_SECONDS,
        nx=True,
    )
    if not single_ok:
        return {
            "blocked": True,
            "reason": "too_fast_same_action",
            "message": RATE_LIMIT_SINGLE_MSG,
            "retry_after": RATE_LIMIT_SINGLE_SECONDS,
        }

    return {
        "blocked": False,
        "reason": "",
        "message": "",
        "retry_after": 0,
    }
