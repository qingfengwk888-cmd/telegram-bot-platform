from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
legacy_path = ROOT / "app" / "legacy_app.py"
out_path = ROOT / "app" / "services" / "rate_limit_service.py"

text = legacy_path.read_text(encoding="utf-8")

names = [
    "normalize_rate_action",
    "bot_user_rate_action_key",
    "bot_user_rate_mute_notice_key",
    "bot_user_rate_burst_key",
    "bot_user_rate_mute_key",
    "is_duplicate_update",
    "get_bot_user_rate_limit_status",
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

header = '''from typing import Optional

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


'''

content = header + "\n\n\n".join(blocks) + "\n"

out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(content, encoding="utf-8")

print("✅ wrote app/services/rate_limit_service.py")
print(f"blocks={len(blocks)}")
if missing:
    print("⚠️ missing:")
    for x in missing:
        print(" -", x)

if not blocks:
    raise SystemExit("❌ 没抽到任何函数")
