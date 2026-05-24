from pathlib import Path
import re

path = Path("app/legacy_app.py")
text = path.read_text(encoding="utf-8")

# 加入新 lifespan import
if "from app.core.lifespan import lifespan" not in text:
    text = text.replace(
        "from app.core.logger import logger\n",
        "from app.core.logger import logger\nfrom app.core.lifespan import lifespan\n",
        1,
    )

# 删除旧 lifespan 函数
pattern = r"\n@asynccontextmanager\nasync def lifespan\(app: FastAPI\):.*?(?=\napp = FastAPI)"
text2, n = re.subn(pattern, "\n", text, count=1, flags=re.S)

print("old lifespan removed =", n)

if n != 1:
    raise SystemExit("❌ 没找到旧 lifespan 函数，请把 nl -ba app/legacy_app.py | sed -n '230,285p' 输出发我")

path.write_text(text2, encoding="utf-8")
print("✅ legacy_app.py now uses app.core.lifespan")
