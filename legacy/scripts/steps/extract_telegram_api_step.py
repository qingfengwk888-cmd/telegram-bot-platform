from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
legacy_path = ROOT / "app" / "legacy_app.py"
out_path = ROOT / "app" / "telegram" / "api.py"

text = legacy_path.read_text(encoding="utf-8")

names = [
    "telegram_raw",
    "tg",
    "register_bot_commands",
    "register_bot_commands_safe",
]

blocks = []
missing = []

for name in names:
    pattern = rf"\nasync def {name}\(.*?(?=\n(?:async def|def) )"
    m = re.search(pattern, text, flags=re.S)
    if not m:
        missing.append(name)
        continue
    blocks.append(m.group(0).strip())

content = '''import json
import time
from typing import Optional

import httpx

from app.core.logger import logger
from app.utils.helpers import cost_ms, safe_json_dumps

telegram_http_client: Optional[httpx.AsyncClient] = None


def set_telegram_http_client(client: Optional[httpx.AsyncClient]) -> None:
    global telegram_http_client
    telegram_http_client = client


''' + "\n\n\n".join(blocks) + "\n"

out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(content, encoding="utf-8")

print("✅ wrote app/telegram/api.py")
if missing:
    print("⚠️ missing:")
    for x in missing:
        print(" -", x)
