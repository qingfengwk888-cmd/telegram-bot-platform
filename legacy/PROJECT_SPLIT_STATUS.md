# PROJECT_SPLIT_STATUS

## 当前状态

telegram-bot-platform 已完成旧单文件 legacy_app 拆分。

## 入口

- 当前运行入口：`app/main.py`
- FastAPI app 创建与路由挂载已迁入 `app/main.py`
- `app/legacy_app.py` 已删除

## legacy_app 状态

- 剩余顶层函数：0
- active app/scripts 源码中无 `legacy_app` 依赖
- 旧拆分脚本已归档到 `legacy/scripts/steps/`
- 原始历史文件与备份保留在 `legacy/`

## 当前 scripts 目录

保留运行/维护脚本：

- `scripts/init_db.py`
- `scripts/migrate_redis_to_db.py`
- `scripts/report_legacy_functions.py`

## 验证命令

    python -m py_compile \
      app/main.py app/routes/*.py app/services/*.py app/telegram/*.py app/core/*.py app/storage/*.py scripts/*.py

    timeout 8s python -m app.main
    echo "exit_code=$?"

    python scripts/report_legacy_functions.py

    grep -R "from app.legacy_app\|import app.legacy_app\|import legacy_app\|from app import legacy_app" -n app scripts \
      --exclude-dir=__pycache__ \
      --exclude="*.pyc" || true

## 最终确认标准

- `exit_code=0`
- `legacy_app.py remaining top-level functions: 0`
- `app/legacy_app.py not found`
- active `app/` 与 `scripts/` 中无 legacy_app import
- `git status` clean
