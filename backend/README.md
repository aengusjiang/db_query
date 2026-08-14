# db_query Backend

数据库查询工作台的后端服务（Python 3.12 + FastAPI）。

- 注册 PostgreSQL / MySQL 连接，浏览 Schema
- 执行只读 SELECT 查询（自动 LIMIT 1000）
- OpenAI 自然语言转 SQL（NL2SQL）
- 应用自身数据存 SQLite（`~/.db_query/db_query.db`）

## 快速开始

```bash
cd backend
cp .env.example .env   # 填入 OPENAI_API_KEY（必填，缺失会导致启动失败）
uv sync --extra dev
uv run uvicorn app.main:app --reload --port 8000
```

完整说明见根目录 [`CLAUDE.md`](../CLAUDE.md) 与 [`docs/架构与开发指南.md`](../docs/架构与开发指南.md)。
