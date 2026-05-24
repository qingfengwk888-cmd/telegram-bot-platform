from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "app" / "legacy_app.py"
text = path.read_text(encoding="utf-8")

names = [
    "format_button_preview",
    "format_all_tenants_text",
    "format_tenant_summary_text",
    "format_started_users_text",
    "format_tenant_category_text",
    "build_apply_summary",
    "build_creator_signature",
    "build_final_welcome_text",
]

removed = []

for name in names:
    pattern = rf"\n(?:async def|def) {name}\(.*?(?=\n(?:async def|def) )"
    text, n = re.subn(pattern, "\n", text, count=1, flags=re.S)
    print(f"{name}: removed={n}")
    if n == 1:
        removed.append(name)

import_block = "from app.telegram.formatters import (\n"
for name in names:
    import_block += f"    {name},\n"
import_block += ")\n"

if "from app.telegram.formatters import" not in text:
    text = text.replace(
        "from fastapi.responses import JSONResponse\n",
        "from fastapi.responses import JSONResponse\n" + import_block,
        1,
    )

path.write_text(text, encoding="utf-8")
print(f"✅ removed {len(removed)} formatter functions and added import")
