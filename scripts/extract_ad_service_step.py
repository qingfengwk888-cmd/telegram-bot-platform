from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
legacy_path = ROOT / "app" / "legacy_app.py"
out_path = ROOT / "app" / "services" / "ad_service.py"

text = legacy_path.read_text(encoding="utf-8")

names = [
    "platform_ad_config_key",
    "load_platform_ad_config",
    "save_platform_ad_config",
    "delete_platform_ad_config",
    "generate_ad_id",
    "normalize_ad_item",
]

blocks = []
missing = []

for name in names:
    pattern = rf"\n(?:async def|def) {name}\(.*?(?=\n(?:async def|def|@app\.|# =+) )"
    m = re.search(pattern, text, flags=re.S)
    if not m:
        missing.append(name)
        continue
    blocks.append(m.group(0).strip())

header = '''from typing import Optional, List, Dict, Any
import uuid

from app.storage.redis_compat import redis_client
from app.storage.repository import redis_get_json_db, redis_set_json_db, kv_delete_db
from app.utils.helpers import now_ms


'''

content = header + "\n\n\n".join(blocks) + "\n"

out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(content, encoding="utf-8")

print("✅ wrote app/services/ad_service.py")
print(f"blocks={len(blocks)}")
if missing:
    print("⚠️ missing:")
    for x in missing:
        print(" -", x)

if not blocks:
    raise SystemExit("❌ 没抽到任何广告相关函数，先看 grep 输出")
