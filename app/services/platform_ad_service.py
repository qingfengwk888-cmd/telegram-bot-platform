from typing import List, Optional

from app.services.ad_service import load_platform_ad_config, save_platform_ad_config


async def list_platform_ads() -> List[dict]:
    data = await load_platform_ad_config()
    items = (data or {}).get("items") or []
    if not isinstance(items, list):
        return []
    return items


async def get_platform_ad_by_id(ad_id: str) -> Optional[dict]:
    items = await list_platform_ads()
    for item in items:
        if str(item.get("adId") or "") == str(ad_id):
            return item
    return None


async def save_platform_ads(items: List[dict]) -> None:
    await save_platform_ad_config({"items": items})
