from pathlib import Path
import re

path = Path("app/legacy_app.py")
text = path.read_text(encoding="utf-8")

names = [
    "cost_ms",
    "now_ms",
    "json_response",
    "safe_json_dumps",
    "sanitize_tenant_id",
    "format_date_ymd",
    "is_primary_platform_admin",
    "is_secondary_platform_admin",
    "build_bot_id_from_bot_username",
    "build_tenant_id_from_admin_chat_id",
    "escape_html",
    "mask_bot_token",
    "is_skip_text",
    "get_today_ymd",
    "is_same_ymd_ts_ms",
    "build_user_link",
]

for name in names:
    pattern = rf"\ndef {name}\(.*?(?=\n(?:async def|def|@app\.|# =+) )"
    text, n = re.subn(pattern, "\n", text, count=1, flags=re.S)
    print(f"{name}: removed={n}")

# 先删除旧的 helpers import 块，避免重复/缺项
text = re.sub(
    r"from app\.utils\.helpers import \([\s\S]*?\)\n",
    "",
    text,
    count=10,
)

import_block = "from app.utils.helpers import (\n"
for name in names:
    import_block += f"    {name},\n"
import_block += ")\n"

text = text.replace(
    "from fastapi.responses import JSONResponse\n",
    "from fastapi.responses import JSONResponse\n" + import_block,
    1,
)

path.write_text(text, encoding="utf-8")
print("✅ legacy_app.py now uses shared helpers")
