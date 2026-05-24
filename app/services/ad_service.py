import time
from typing import Optional, List, Dict, Any
import uuid

from app.storage.redis_compat import redis_client
from app.storage.repository import redis_get_json_db, redis_set_json_db, kv_delete_db
from app.utils.helpers import now_ms

# 兼容 legacy_app 里的旧函数名
redis_get_json = redis_get_json_db
redis_set_json = redis_set_json_db


def platform_ad_config_key() -> str:
    return "platform:ad:config"


async def load_platform_ad_config() -> Optional[dict]:
    return await redis_get_json(platform_ad_config_key())


async def save_platform_ad_config(data: dict) -> None:
    await redis_set_json(platform_ad_config_key(), data)


async def delete_platform_ad_config() -> None:
    await redis_client.delete(platform_ad_config_key())


def generate_ad_id() -> str:
    return f"ad_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"


def normalize_ad_item(item: dict) -> dict:
    item = item or {}

    ad_id = str(item.get("adId") or item.get("id") or "").strip()
    if not ad_id:
        ad_id = generate_ad_id()

    return {
        "adId": ad_id,
        "text": str(item.get("text") or "").strip(),
        "url": str(item.get("url") or "").strip(),
        "createdAt": int(item.get("createdAt") or now_ms()),
        "updatedAt": int(item.get("updatedAt") or now_ms()),
    }
