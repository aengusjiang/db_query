# CLAUDE.md

本文件为 Claude Code 提供本项目的工作上下文。完整中文说明见 [`docs/架构与开发指南.md`](docs/架构与开发指南.md)。

## 项目定位

db_query 是自托管的**数据库查询工作台**：注册 PostgreSQL / MySQL 连接，浏览 Schema，执行**只读 SELECT** 查询，并用 OpenAI 把自然语言转成 SQL。

- `backend/` — Python 3.12 + FastAPI（应用自身数据存 SQLite `~/.db_query/db_query.db`）。
- `frontend/` — React 18 + TypeScript + Vite + Ant Design + Monaco（主界面 `pages/Home.tsx`）。
- 无 Docker、无 CI；开发流程统一走根目录 `Makefile`。

## 技术栈速览

- **后端**：FastAPI、SQLModel/SQLAlchemy、asyncpg（PG）、aiomysql/PyMySQL（MySQL）、sqlglot（SQL 校验）、openai SDK（NL2SQL）、Alembic、Pydantic v2。包管理用 `uv`。
- **前端**：React 18、TypeScript 5.9、Vite 7、Ant Design 5、@monaco-editor/react、axios、react-router-dom 7、Tailwind 4、vitest。（Refine 5 为依赖且存在备选页，但当前未挂载。）

## 开发语言与环境

- **语言/运行时**：Python **3.12+**（硬性，`backend/.python-version`）、TypeScript 5.9、Node ≥ 20（Vite 7）。
- **推荐 OS**：**Windows 10 + WSL2 Ubuntu 24.04**（自带 Python 3.12，与宿主及 openEuler 隔离，无需改动服务器 Python；详见指南 §9）；或在 **openEuler 22.03 SP4** 上原生开发（需自行装 3.12，§8）。原因：WSL 体验等同 Linux，避开编译/Make/CRLF；裸机部署同构。
- **注意**：openEuler 默认 Python 是 **3.9.9**，必须另装 3.12（源码编译或 pyenv）；本机 uv / node 也需安装。Windows 10 推荐 WSL2，原生需 Python 3.12 + uv + Node ≥20，无 `make` 时用底层 `uv`/`npm` 命令。详细步骤见 `docs/架构与开发指南.md` 第 8、9 节。
- **IDE**：VSCode + Remote-SSH（已用）；推荐扩展 Python/Pylance/Ruff、ESLint、REST Client、Markdown Preview Mermaid Support。

## 常用命令（以 Makefile 为准）

```bash
make install            # 安装依赖：uv sync --extra dev + npm install
make setup              # install + alembic upgrade head
make dev                # 同时启动前后端（:8000 + :5173）
make dev-backend        # 仅后端：uvicorn app.main:app --reload --port 8000
make dev-frontend       # 仅前端：vite（:5173，/api 代理到 :8000）
make test               # 后端 pytest + 前端 vitest
make test-backend-coverage
make lint               # ruff + eslint
make format             # ruff format + eslint --fix
make backend-check      # mypy + ruff（后端）
make db-upgrade         # alembic upgrade head
make db-migrate MESSAGE="..."
make ci                 # install + lint + test
make help               # 查看全部目标
```

后端入口：`backend/app/main:app`；前端入口：`frontend/src/main.tsx` → `App.tsx` → `Home.tsx`。

## 架构要点（关键：新 / 旧双实现并存）

后端分层，依赖自上而下：

- **API 层** `app/api/v1/`：`databases.py`、`queries.py`（前缀均为 `/api/v1/dbs`，另有 `/health`）。
- **新路径（推荐，查询走这里）**：`services/database_service.py`（`DatabaseService` Facade）+ `adapters/`（`base.DatabaseAdapter` ABC + `registry.DatabaseAdapterRegistry` 工厂，按 `type:name` 缓存实例）+ 具体适配器 `postgresql.py`(asyncpg)、`mysql.py`(aiomysql)。
- **旧路径（元数据仍在用）**：`services/metadata.py` + `connection_factory.py` + `db_connection.py`(PG 池) + `mysql_*.py`。
- **横切**：`services/sql_validator.py`（仅 SELECT + 自动 LIMIT 1000）、`services/nl2sql.py`（`gpt-4o-mini`，temp 0.1）。
- **持久化**：`app/models/`（SQLModel 表：`databaseconnections` / `databasemetadata` / `queryhistory`）+ `schemas.py`（Pydantic DTO，全局 camelCase 别名）。

查询端到端：`POST /api/v1/dbs/{name}/query` → `query_wrapper.execute_query_with_service` → `DatabaseService.execute_query`（校验 + 取适配器）→ `adapter.execute_query`（连接池 → DB）→ `save_query_history`（成功/失败均落库，每库保留 50 条）。

## 代码约定

- **后端**：Python 3.12；`ruff`（line-length 100，`target-version=py312`，规则 `E,F,I,N,W,UP`）；`mypy` 严格（`disallow_untyped_defs`）；`pytest`（`asyncio_mode=auto`）。API DTO 用 camelCase 别名。
- **前端**：TypeScript strict；Vite 配置 `@ → ./src` 别名，`/api` 代理到 `http://localhost:8000`。

## 关键约束与坑

- **`OPENAI_API_KEY` 必填**：`backend/.env` 缺失会导致 backend 启动即崩（`config.py` 无默认值）。
- **仅 SELECT**：非 SELECT 一律 400；无 LIMIT 自动补 `LIMIT 1000`。
- **连接 URL 明文存储**：`databaseconnections.url` 可能含密码，生产需评估风险。
- **前端双锁文件**：`package-lock.json` + `yarn.lock` 并存；Makefile 用 npm，建议删掉 `yarn.lock`。
- **无 Node 版本锁定**：需 Node ≥ 20（Vite 7 要求）。
- **`make clean-db`** 会删除 `~/.db_query/db_query.db`（全部连接/历史）。
- `main.py`：导入时与 startup 都会 `init_db()`（`create_all`），故不跑 Alembic 也能用；shutdown 关闭旧路径 PG 连接池。

## 深入阅读

- 完整中文指南：[`docs/架构与开发指南.md`](docs/架构与开发指南.md)（含 Mermaid 架构图、API 表、搭建步骤、自检清单）。
- 架构重构计划：`docs/ARCHITECTURE_REDESIGN.md`、`docs/ARCHITECTURE_INDEX.md`。
- 新增适配器：`backend/app/adapters/README.md`、`docs/QUICK_REFERENCE.md`。
- 接口测试用例：`fixtures/test.rest`（VSCode REST Client）。
- 样例数据库：`backend/scripts/`（MySQL `interview_db`）。
