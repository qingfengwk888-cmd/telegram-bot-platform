from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
legacy_path = ROOT / "app" / "legacy_app.py"
out_path = ROOT / "app" / "services" / "bot_service.py"

text = legacy_path.read_text(encoding="utf-8")

names = [
    "load_bot_by_bot_username",
    "load_bot",
    "save_bot",
    "get_bot_index",
    "add_bot_index",
    "remove_bot_index",
    "pick_default_bot_for_tenant",
    "pick_sender_bot_for_tenant",
    "list_started_users",
    "save_started_user_profile",
    "set_bot_user_blacklisted",
    "is_bot_user_blacklisted",
]

blocks = []
missing = []

for name in names:
    pattern = rf"\nasync def {name}\(.*?(?=\n(?:async def|def|@app\.|# =+) )"
    m = re.search(pattern, text, flags=re.S)
    if not m:
        missing.append(name)
        continue
    blocks.append(m.group(0).strip())

header = '''import time
from typing import List, Optional

from app.core.logger import logger
from app.utils.helpers import (
    cost_ms,
    sanitize_tenant_id,
    build_bot_id_from_bot_username,
)
from app.storage.repository import (
    load_bot_db,
    save_bot_db,
    get_bot_index_db,
    get_latest_bot_id_by_tenant_id_db,
    list_started_users_by_bot_id_db,
    save_started_user_profile_db,
    set_bot_user_blacklisted_db,
    is_bot_user_blacklisted_db,
)


'''

content = header + "\n\n\n".join(blocks) + "\n"

out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(content, encoding="utf-8")

print("✅ wrote app/services/bot_service.py")
print(f"blocks={len(blocks)}")
if missing:
    print("⚠️ missing:")
    for x in missing:
        print(" -", x)

if not blocks:
    raise SystemExit("❌ 没抽到任何函数，检查 legacy_app.py 里函数是否还存在")
