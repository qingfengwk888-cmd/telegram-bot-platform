from typing import Optional

from app.config import MESSAGE_MAP_TTL_SECONDS
from app.storage.repository import redis_get_json_db, redis_set_json_db
from app.utils.helpers import now_ms, sanitize_tenant_id


def platform_tenant_notice_map_key(message_id: int) -> str:
    return f"platform:tenant_notice_map:{int(message_id)}"


async def map_platform_notice_message(message_id: int, tenant_id: str, applicant_chat_id: int) -> None:
    await redis_set_json_db(
        platform_tenant_notice_map_key(message_id),
        {
            "tenantId": sanitize_tenant_id(tenant_id),
            "applicantChatId": int(applicant_chat_id),
            "ts": now_ms(),
        },
        MESSAGE_MAP_TTL_SECONDS,
    )


async def get_platform_notice_target(message_id: int) -> Optional[dict]:
    return await redis_get_json_db(platform_tenant_notice_map_key(message_id))
