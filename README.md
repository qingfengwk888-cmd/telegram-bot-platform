# telegram-bot-platform

目标：从 Replit 单文件 + Redis 存储，迁移为 Codespaces/VPS 可维护项目结构。

原则：
1. 不重写原项目业务逻辑。
2. 先拆结构，再替换存储层。
3. 原来的 Redis 读写函数名尽量保留，用数据库实现兼容。
4. 测试机器人 Token 独立配置，不影响线上 Replit 项目。
