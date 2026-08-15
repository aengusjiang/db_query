-- Sample HR database for PostgreSQL
-- 用途：db_query 工作台的 PostgreSQL 演示库（与 MySQL 侧 interview_db 对应）
-- 执行方式（WSL Ubuntu）：
--   wsl -d Ubuntu -u root -- su - postgres -c "psql -f /mnt/e/workspace/db_query/backend/scripts/create_sample_hr.sql"
-- 账号：dbquery_ro / dbquery123（只读 SELECT，与 MySQL 侧 dbquery 同策略）
-- 注意：以下密码为本地演示专用弱口令，严禁复制到任何生产环境

CREATE USER dbquery_ro WITH PASSWORD 'dbquery123';

CREATE DATABASE sample_hr ENCODING 'UTF8' TEMPLATE template0;

\connect sample_hr

CREATE TABLE departments (
    id   SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    location VARCHAR(100)
);

CREATE TABLE employees (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(50) NOT NULL,
    email         VARCHAR(200) NOT NULL UNIQUE,
    department_id INT NOT NULL REFERENCES departments(id),
    title         VARCHAR(100) NOT NULL,
    hire_date     DATE NOT NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE salary_history (
    id             SERIAL PRIMARY KEY,
    employee_id    INT NOT NULL REFERENCES employees(id),
    annual_salary  NUMERIC(12, 2) NOT NULL,
    effective_from DATE NOT NULL
);

INSERT INTO departments (name, location) VALUES
    ('技术部', '北京总部 3 层'),
    ('产品部', '北京总部 5 层'),
    ('市场部', '上海分部'),
    ('人事部', '北京总部 1 层'),
    ('财务部', '深圳分部');

INSERT INTO employees (name, email, department_id, title, hire_date, is_active) VALUES
    ('张伟',   'zhang.wei@example.com',   1, '首席架构师',       '2019-03-11', TRUE),
    ('王芳',   'wang.fang@example.com',   1, '高级后端工程师',   '2020-07-01', TRUE),
    ('李强',   'li.qiang@example.com',    1, '前端开发工程师',   '2021-11-15', TRUE),
    ('刘洋',   'liu.yang@example.com',    1, 'DevOps 工程师',    '2022-02-14', TRUE),
    ('陈静',   'chen.jing@example.com',   1, '测试开发工程师',   '2022-09-05', TRUE),
    ('杨帆',   'yang.fan@example.com',    2, '产品总监',         '2019-06-18', TRUE),
    ('赵磊',   'zhao.lei@example.com',    2, '高级产品经理',     '2021-01-11', TRUE),
    ('黄晓明', 'huang.xiaoming@example.com', 2, '产品助理',       '2023-04-03', TRUE),
    ('周涛',   'zhou.tao@example.com',    3, '市场总监',         '2020-10-26', TRUE),
    ('吴敏',   'wu.min@example.com',      3, '内容运营专员',     '2022-06-20', TRUE),
    ('徐丽',   'xu.li@example.com',       3, '品牌经理',         '2021-08-09', FALSE),
    ('孙浩',   'sun.hao@example.com',     4, 'HR 经理',          '2019-12-02', TRUE),
    ('马丽',   'ma.li@example.com',       4, '招聘专员',         '2022-03-28', TRUE),
    ('朱军',   'zhu.jun@example.com',     5, '财务总监',         '2018-05-21', TRUE),
    ('胡雪',   'hu.xue@example.com',      5, '会计',             '2021-02-08', TRUE),
    ('林峰',   'lin.feng@example.com',    1, '算法工程师',       '2023-01-16', TRUE),
    ('何雨',   'he.yu@example.com',       2, '数据分析师',       '2022-11-30', TRUE),
    ('高翔',   'gao.xiang@example.com',   1, '安全工程师',       '2020-04-13', FALSE),
    ('罗丹',   'luo.dan@example.com',     3, '渠道经理',         '2021-05-17', TRUE),
    ('郑凯',   'zheng.kai@example.com',   1, '数据库管理员',     '2019-09-23', TRUE);

INSERT INTO salary_history (employee_id, annual_salary, effective_from) VALUES
    (1,  720000.00, '2019-03-11'),
    (1,  860000.00, '2022-01-01'),
    (2,  410000.00, '2020-07-01'),
    (2,  495000.00, '2023-01-01'),
    (3,  330000.00, '2021-11-15'),
    (4,  350000.00, '2022-02-14'),
    (5,  305000.00, '2022-09-05'),
    (6,  640000.00, '2019-06-18'),
    (6,  780000.00, '2023-01-01'),
    (7,  420000.00, '2021-01-11'),
    (8,  220000.00, '2023-04-03'),
    (9,  560000.00, '2020-10-26'),
    (10, 260000.00, '2022-06-20'),
    (11, 300000.00, '2021-08-09'),
    (12, 430000.00, '2019-12-02'),
    (13, 250000.00, '2022-03-28'),
    (14, 680000.00, '2018-05-21'),
    (15, 280000.00, '2021-02-08'),
    (16, 470000.00, '2023-01-16'),
    (17, 390000.00, '2022-11-30'),
    (18, 380000.00, '2020-04-13'),
    (19, 340000.00, '2021-05-17'),
    (20, 450000.00, '2019-09-23');

-- 只读授权
GRANT USAGE ON SCHEMA public TO dbquery_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO dbquery_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO dbquery_ro;
