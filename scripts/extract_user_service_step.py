from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
legacy_path = ROOT / "app" / "legacy_app.py"
out_path = ROOT / "app" / "services" / "user_service.py"

text = legacy_path.read_text(encoding="utf-8")

names = [
    "find_bot_button_reply",
    "bot_user_profile_key",
    "check_bot_start_alert",
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
    START_ALERT_WINDOW_SECONDS,
    START_ALERT_THRESHOLD,
    START_ALERT_COOLDOWN_SECONDS,
)
from app.core.logger import logger
from app.storage.redis_compat import redis_client
from app.telegram.api import tg
from app.utils.helpers import now_ms


'''

content = header + "\n\n\n".join(blocks) + "\n"

out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(content, encoding="utf-8")

print("✅ wrote app/services/user_service.py")
print(f"blocks={len(blocks)}")
if missing:
    print("⚠️ missing:")
    for x in missing:
        print(" -", x)

if not blocks:
    raise SystemExit("❌ 没抽到任何 user/profile 函数")
