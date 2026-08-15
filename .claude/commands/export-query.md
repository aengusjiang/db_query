---
description: 一键"执行查询 + 导出结果"为 CSV/JSON 文件（走后端导出 API）
argument-hint: [连接名] [SQL] [csv|json]
---

# 导出查询结果

把一条 SELECT 查询的结果导出为 CSV 或 JSON 文件。任务分三步：**获取查询结果 → 格式化校验 → 创建文件**。

参数：`$ARGUMENTS`（依次为：连接名、SQL 语句、格式 csv|json）。

## 第 0 步：核对参数

- 三个参数不全时，**先问用户再行动，不要猜**：
  - 连接名不确定 → 调用 `curl -s http://localhost:8000/api/v1/dbs` 列出已注册连接让用户选；
  - SQL 未提供 → 询问要导出什么数据；
  - 格式未指定 → 默认 `csv`（并告知用户）。
- SQL 必须以 SELECT 开头（后端仅放行只读查询）。

## 第 1 步：获取查询结果（执行 + 导出一次完成）

后端起着（否则先 `make dev-backend`），调用导出 API（该接口内置 sqlglot 校验、自动 LIMIT 1000、查询历史落库）：

```bash
mkdir -p exports
curl -sS -D /tmp/export_headers.txt -o "exports/<连接名>_$(date -u +%Y%m%dT%H%M%S).<格式>" \
  -X POST "http://localhost:8000/api/v1/dbs/<连接名>/export" \
  -H "Content-Type: application/json" \
  -d '{"sql": "<SQL>", "format": "<格式>"}'
```

## 第 2 步：格式化校验（错误分诊）

读取 `/tmp/export_headers.txt` 按状态码分诊：

| 状态码 | 含义 | 处理 |
|---|---|---|
| 200 | 成功 | 进入第 3 步 |
| 404 | 连接不存在 | 列出可用连接（`GET /api/v1/dbs`），让用户重选 |
| 400 | SQL 校验失败（非 SELECT 等） | 把 detail 转告用户，请其修正 SQL |
| 422 | format 非法 / sql 为空 | 修正参数重试 |
| 500 | 数据库执行错误 | 转告 detail（如表不存在），建议核对表名/权限 |

成功后继续校验内容：

- `X-Row-Count` 等于 `1000` → 明确告知用户"结果触达自动 LIMIT 1000 上限，可能被截断"；
- csv 格式 → `head -c 3 <文件> | xxd` 应以 `efbbbf`（UTF-8 BOM）开头，保证 Excel 中文不乱码；
- json 格式 → `jq . <文件>` 能解析且为对象数组。

## 第 3 步：创建文件并报告

- 文件已由第 1 步 `-o` 落盘到 `exports/`（该目录已被 .gitignore 忽略）；
- 用 `ls -lh` 确认文件存在，向用户报告：**文件路径、行数（X-Row-Count）、格式、是否触发 1000 行截断**；
- 若用户在 WSL 环境，提醒 Windows 侧可通过 `\\wsl$\Ubuntu\home\<user>\db_query\exports\` 访问文件。

## 示例

```
/export-query interview-db "SELECT first_name, last_name, current_title FROM candidates LIMIT 10" csv
/export-query sample-hr "SELECT e.name, d.name AS dept FROM employees e JOIN departments d ON d.id = e.department_id" json
```
