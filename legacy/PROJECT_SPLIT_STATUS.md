# Telegram Bot Platform 拆分进度摘要

## 当前目标
项目继续从 app/legacy_app.py 小步拆分到 app/services、app/core、app/telegram、app/routes 等模块。
原则是：不重写项目、不改页面排版、不改通知文案、不改按钮文案，每一步拆完都要编译、启动测试、提交。

## 当前注意事项
- 不要改变平台机器人页面排版。
- 不要改变数据概览、租户详情、用户列表、黑名单列表、通知文案排版。
- 展示类函数只能原样搬运，不能重写。
- internal_service 自动抽取失败过，暂时不要继续拆 internal_*。
- platform_display_service 重写版曾改变排版，已经回滚，不要再用重写版。
- try_handle_platform_blacklist_command 暂时不要拆，里面存在 callback_query["id"] 未定义风险点。
- handle_platform_message、handle_platform_callback_query、handle_bot_callback_query 都是大函数，后续只能拆内部小分支，不要整函数搬。
- 当前 apply/接入机器人逻辑符合预期：提交机器人后自动接入，管理员只收到启动/接入通知，不需要逐个点同意。

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
- app/core/request_helpers.py
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
- app/services/message_classify_service.py
- app/services/platform_ad_service.py
- app/services/tenant_query_service.py
- app/services/input_session_service.py
- app/services/message_parse_service.py
- app/services/platform_notice_view_service.py
- app/services/bot_onboarding_service.py
- app/services/platform_dashboard_view_service.py
- app/services/bot_user_blacklist_command_service.py
- app/services/admin_message_service.py
- app/services/user_message_service.py

## 最近完成
- move platform dashboard view helpers to service
- move bot onboarding helpers to service
- move bot user blacklist command handler to service
- move admin message handler to service
- move user message handler to service

## 当前剩余 top-level functions
当前剩余约 13 个，以下以 scripts/report_legacy_functions.py 输出为准：

- try_handle_platform_blacklist_command
- handle_platform_message
- handle_platform_callback_query
- handle_bot_callback_query
- internal_create_bot
- internal_get_tenant
- internal_list_tenants
- internal_list_applies
- internal_disable_tenant
- internal_enable_tenant
- internal_delete_tenant
- internal_setup_webhook
- internal_setup_platform_webhook

## 下一步建议
先不要继续拆 internal_*。
先不要拆 try_handle_platform_blacklist_command。
下一步如果继续拆，优先从 handle_bot_callback_query 或 handle_platform_callback_query 里拆很小的内部功能分支，拆前必须先看完整依赖。

## 下个对话开始时建议执行
cd /workspaces/telegram-bot-platform
git status
git log --oneline -20
python -m py_compile app/main.py app/legacy_app.py app/routes/*.py app/services/*.py app/telegram/*.py app/core/*.py app/storage/*.py
timeout 8s python -m app.main
echo "exit_code=$?"
python scripts/report_legacy_functions.py | head -100

## Latest progress

- `handle_platform_message` has been moved out of `legacy_app.py`.
- `handle_platform_callback_query` has been moved out of `legacy_app.py`.
- `handle_bot_callback_query` has been moved out of `legacy_app.py`.
- `try_handle_platform_blacklist_command` has been moved to service.
- `legacy_app.py` now only keeps internal API compatibility handlers.
- Per current rule, `internal_*` is not being split in this stage.

## 2026-05-24 更新

本轮已完成 service 层 legacy_app 依赖清理。

已清理：
- active app/scripts 源码中已无 legacy_app 依赖
- app/telegram/formatters.py 对 legacy_app 的依赖
- blacklist_service.py 中租户维度黑名单兼容逻辑已迁为基于 tenant 下 bot 汇总判断

当前剩余：
- app/routes/internal.py 仍调用 legacy_app.internal_*，按计划暂不拆
- legacy_app.py 顶层仅保留 internal_* 相关函数

下一步：
- 如继续拆分，可开始迁移 internal_* 到独立 internal service
- 拆 internal_* 前需要先分析 create/setup webhook 相关依赖，避免影响内部 API
