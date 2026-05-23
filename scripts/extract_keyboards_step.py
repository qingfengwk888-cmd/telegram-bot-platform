from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
legacy_path = ROOT / "app" / "legacy_app.py"
keyboards_path = ROOT / "app" / "telegram" / "keyboards.py"

text = legacy_path.read_text(encoding="utf-8")

names = [
    "build_bot_pick_buttons",
    "build_my_bots_action_buttons",
    "build_button_flow_action_buttons",
    "build_global_broadcast_confirm_buttons",
    "build_global_broadcast_target_buttons",
    "build_modify_confirm_buttons",
    "build_my_bots_entry_buttons",
    "build_single_bot_action_buttons",
    "build_button_manage_menu_buttons",
    "build_button_delete_pick_buttons",
    "build_button_reply_map",
    "build_profile_buttons",
    "flatten_welcome_buttons",
    "rebuild_button_rows",
    "build_remove_confirm_buttons",
    "build_platform_reply_keyboard_for_admin",
    "build_bot_reply_keyboard",
    "build_platform_ad_menu_buttons",
    "build_platform_ad_pick_buttons",
    "build_platform_reply_keyboard_for_tenant",
    "build_admin_tenant_pick_buttons",
    "build_admin_tenant_root_menu_buttons",
    "build_admin_tenant_traffic_sort_buttons",
    "build_admin_tenant_category_buttons",
    "build_admin_tenant_pick_buttons_with_back",
    "build_tenant_category_buttons",
    "build_tenant_detail_category_buttons",
    "build_tenant_detail_action_buttons",
    "build_new_tenant_notice_buttons",
    "build_apply_approve_buttons",
    "build_welcome_buttons",
]

blocks = []
missing = []

for name in names:
    pattern = rf"\ndef {name}\(.*?(?=\n(?:async def|def) )"
    m = re.search(pattern, text, flags=re.S)
    if not m:
        missing.append(name)
        continue

    blocks.append(m.group(0).strip())

content = '''from typing import List, Dict

from app.config import PLATFORM_ADMIN_CHAT_ID, PLATFORM_SECONDARY_ADMIN_CHAT_IDS
from app.utils.helpers import escape_html


def is_primary_platform_admin(chat_id: int) -> bool:
    return int(chat_id) == int(PLATFORM_ADMIN_CHAT_ID)


def is_secondary_platform_admin(chat_id: int) -> bool:
    return int(chat_id) in PLATFORM_SECONDARY_ADMIN_CHAT_IDS


''' + "\n\n\n".join(blocks) + "\n"

keyboards_path.parent.mkdir(parents=True, exist_ok=True)
keyboards_path.write_text(content, encoding="utf-8")

print("✅ wrote app/telegram/keyboards.py")
if missing:
    print("⚠️ missing:")
    for x in missing:
        print(" -", x)
