from pathlib import Path
import re

path = Path("app/legacy_app.py")
text = path.read_text(encoding="utf-8")

names = [
    "platform_tenant_notice_map_key",
    "map_platform_notice_message",
    "get_platform_notice_target",
]

for name in names:
    pattern = rf"\n(?:async def|def) {name}\(.*?(?=\n(?:async def|def|@app\.|# =+) )"
    text, n = re.subn(pattern, "\n", text, count=1, flags=re.S)
    print(f"{name}: removed={n}")

import_block = """from app.services.notice_service import (
    platform_tenant_notice_map_key,
    map_platform_notice_message,
    get_platform_notice_target,
)
"""

if "from app.services.notice_service import" not in text:
    text = text.replace(
        "from fastapi.responses import JSONResponse\n",
        "from fastapi.responses import JSONResponse\n" + import_block,
        1,
    )

path.write_text(text, encoding="utf-8")
print("✅ legacy_app.py now uses notice_service")
