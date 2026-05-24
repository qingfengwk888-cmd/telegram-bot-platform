from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "app" / "legacy_app.py"
text = path.read_text(encoding="utf-8")

# 1. 加 import
import_block = '''from app.telegram.api import (
    tg,
    telegram_raw,
    register_bot_commands,
    register_bot_commands_safe,
    set_telegram_http_client,
)
'''

if "from app.telegram.api import" not in text:
    text = text.replace(
        "from fastapi.responses import JSONResponse\n",
        "from fastapi.responses import JSONResponse\n" + import_block,
        1,
    )

# 2. 删除 legacy_app.py 里的 API 函数定义
names = [
    "telegram_raw",
    "tg",
    "register_bot_commands",
    "register_bot_commands_safe",
]

for name in names:
    pattern = rf"\nasync def {name}\(.*?(?=\n(?:async def|def) )"
    text, n = re.subn(pattern, "\n", text, count=1, flags=re.S)
    print(f"{name}: removed={n}")

# 3. 替换全局 telegram_http_client 初始化
text = text.replace(
    "telegram_http_client: Optional[httpx.AsyncClient] = None\n",
    "# telegram_http_client 已迁移到 app.telegram.api\n",
    1,
)

# 4. lifespan 里赋值给 API 模块
text = text.replace(
    '''    telegram_http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )
''',
    '''    telegram_http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )
    set_telegram_http_client(telegram_http_client)
''',
    1,
)

text = text.replace(
    '''        if telegram_http_client is not None:
            await telegram_http_client.aclose()
            telegram_http_client = None
''',
    '''        if telegram_http_client is not None:
            await telegram_http_client.aclose()
            telegram_http_client = None
            set_telegram_http_client(None)
''',
    1,
)

path.write_text(text, encoding="utf-8")
print("✅ legacy_app.py now uses app.telegram.api")
