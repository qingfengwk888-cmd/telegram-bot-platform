# Telegram Bot Platform 拆分进度摘要

## 当前目标
这个项目原本是 Replit 上的单文件 Python 项目，Redis 存储。现在在 Codespace 重建，目标不是重写项目，而是在保持原业务逻辑和排版不变的前提下：
1. Redis 数据迁移到数据库/兼容层
2. 将 legacy_app.py 逐步拆分成合理项目结构
3. 每一步都小步提交，确保 Telegram 平台机器人和测试子机器人能正常运行

## 当前注意事项
- 不要改变平台机器人页面排版。
- 不要改变数据概览、租户详情、用户列表、黑名单列表、通知文案排版。
- 展示类函数如果要拆，只能原样搬运，不能重写。
- internal_service 自动抽取失败过，暂时不要继续拆 internal。
- platform_display_service 重写版曾改变排版，已经回滚，不要再用重写版。
- blacklist command handlers 自动抽取失败过，暂时保留在 legacy_app.py。
- apply/接入机器人逻辑当前符合预期：提交机器人后自动接入，管理员只收到启动/接入通知，不需要逐个点同意。

## 已拆分模块
- app/storage/database.py
- app/storage/models.py
- app/storage/repository.py
- app/storage/redis_compat.py
- app/telegram/api.py
- app/telegram/keyboards.py
- app/telegram/formatters.py
- app/routes/health.py
- app/routes/platform.py
- app/routes/webhook.py
- app/routes/internal.py
- app/core/lifespan.py
- app/core/keys.py
- app/services/tenant_service.py
- app/services/bot_service.py
- app/services/rate_limit_service.py
- app/services/ad_service.py
- app/services/notice_service.py
- app/services/blacklist_service.py
- app/services/user_service.py
- app/services/lock_service.py
- app/services/stat_service.py
- app/services/reply_service.py

## 最近完成
- move redis key builders to core keys module
- move lock helpers to lock service
- move stat helpers to stat service
- move rate limit reply helpers to reply service
- internal_service 抽取不安全，已删除/放弃，不接入
- platform_display_service 因改变排版已回滚，不接入

## 当前建议下一步
先重新生成 legacy_app.py 剩余函数清单，再决定下一步拆分。
优先拆小型、纯逻辑、不会改变排版的函数。
暂时避开：
- handle_platform_message
- handle_platform_callback_query
- handle_bot_callback_query
- handle_user_message
- handle_admin_message
- try_handle_platform_blacklist_command
- try_handle_bot_user_blacklist_command
- internal_* 路由函数
- 展示排版函数

## 下个对话开始时建议执行
cd /workspaces/telegram-bot-platform
git status
git log --oneline -10
python -m py_compile app/main.py app/legacy_app.py app/routes/*.py app/services/*.py app/telegram/*.py app/core/*.py app/storage/*.py

python scripts/report_legacy_functions.py | tee legacy/remaining_functions.txt
wc -l app/legacy_app.py
python scripts/report_legacy_functions.py | head -160
