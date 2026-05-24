from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "app" / "legacy_app.py"
text = path.read_text(encoding="utf-8")

names = [
    "platform_ad_config_key",
    "load_platform_ad_config",
    "save_platform_ad_config",
    "delete_platform_ad_config",
    "generate_ad_id",
    "normalize_ad_item",
]

for name in names:
    pattern = rf"\n(?:async def|def) {name}\(.*?(?=\n(?:async def|def|@app\.|# =+) )"
    text, n = re.subn(pattern, "\n", text, count=1, flags=re.S)
    print(f"{name}: removed={n}")

import_block = "from app.services.ad_service import (\n"
for name in names:
    import_block += f"    {name},\n"
import_block += ")\n"

if "from app.services.ad_service import" not in text:
    text = text.replace(
        "from fastapi.responses import JSONResponse\n",
        "from fastapi.responses import JSONResponse\n" + import_block,
        1,
    )

path.write_text(text, encoding="utf-8")
print("✅ legacy_app.py now uses ad_service")
