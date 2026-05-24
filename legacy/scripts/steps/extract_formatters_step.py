from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
legacy_path = ROOT / "app" / "legacy_app.py"
out_path = ROOT / "app" / "telegram" / "formatters.py"

text = legacy_path.read_text(encoding="utf-8")

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

blocks = []
missing = []

for name in names:
    pattern = rf"\n(?:async def|def) {name}\(.*?(?=\n(?:async def|def) )"
    m = re.search(pattern, text, flags=re.S)
    if not m:
        missing.append(name)
        continue
    blocks.append(m.group(0).strip())

content = '''import html
from typing import List, Optional

from app.config import DEFAULT_WELCOME_TEXT
from app.utils.helpers import escape_html, format_date_ymd

# 注意：部分 formatter 暂时仍依赖 legacy_app 内的查询函数。
# 下一步正式替换 import 时再处理这些依赖。


''' + "\n\n\n".join(blocks) + "\n"

out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(content, encoding="utf-8")

print("✅ wrote app/telegram/formatters.py")
if missing:
    print("⚠️ missing:")
    for x in missing:
        print(" -", x)
