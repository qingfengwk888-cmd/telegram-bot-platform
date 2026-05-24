from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
legacy = ROOT / "legacy" / "legacy_main.py"
text = legacy.read_text(encoding="utf-8")

names = [
    "telegram_raw",
    "tg",
    "register_bot_commands",
    "register_bot_commands_safe",
]

blocks = []
for name in names:
    m = re.search(rf"\nasync def {name}\(.*?(?=\n(?:async\s+)?def |\nclass |\n# =+|\Z)", text, re.S)
    if m:
        blocks.append(m.group(0).strip())
    else:
        print(f"⚠️ not found: {name}")

content = '''import httpx
from typing import Optional

from app.core.logger import logger

telegram_http_client: Optional[httpx.AsyncClient] = None


def set_telegram_http_client(client: Optional[httpx.AsyncClient]) -> None:
    global telegram_http_client
    telegram_http_client = client

''' + "\n\n".join(blocks) + "\n"

out = ROOT / "app" / "telegram" / "api.py"
out.write_text(content, encoding="utf-8")
print(f"✅ wrote {out.relative_to(ROOT)}")
