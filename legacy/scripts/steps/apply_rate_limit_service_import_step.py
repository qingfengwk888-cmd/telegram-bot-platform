from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "app" / "legacy_app.py"
text = path.read_text(encoding="utf-8")

names = [
    "normalize_rate_action",
    "bot_user_rate_action_key",
    "bot_user_rate_mute_notice_key",
    "bot_user_rate_burst_key",
    "bot_user_rate_mute_key",
    "is_duplicate_update",
    "get_bot_user_rate_limit_status",
]

for name in names:
    pattern = rf"\n(?:async def|def) {name}\(.*?(?=\n(?:async def|def|@app\.|# =+) )"
    text, n = re.subn(pattern, "\n", text, count=1, flags=re.S)
    print(f"{name}: removed={n}")

import_block = "from app.services.rate_limit_service import (\n"
for name in names:
    import_block += f"    {name},\n"
import_block += ")\n"

if "from app.services.rate_limit_service import" not in text:
    text = text.replace(
        "from fastapi.responses import JSONResponse\n",
        "from fastapi.responses import JSONResponse\n" + import_block,
        1,
    )

path.write_text(text, encoding="utf-8")
print("✅ legacy_app.py now uses rate_limit_service")
