# Cognion

Cognion 是一个面向论文阅读与问答的 AI 文献工作台。它把“上传 PDF → 目录组织 → 阅读标注 → 引用问答 → 历史沉淀”串成一条完整流程。

## 项目结构

- `frontend/`: React + Vite 前端
- `backend/`: FastAPI + SQLAlchemy 后端

## 当前功能（已实现）

### 前端

- 文献库支持多层级文件夹树，搭建完成文件系统
- 阅读区支持 PDF 渲染、缩放、文本引用、LLM 对话
- 右侧 AI 对话区支持 Markdown / 数学公式 / 代码高亮渲染

### 后端

- 上传 PDF 后保存文件并入库论文元信息
- 论文元信息持久化到 PostgreSQL（标题、作者、期刊、摘要等）
- 论文与目录关系持久化（支持移动后同步文件路径）
- 论文问答消息按 `paper_id` 持久化并可回放
- 文件夹树接口返回层级结构与“是否含论文”聚合状态

## 环境要求

- Node.js 18+
- Python 3.10+
- PostgreSQL 14+

## PostgreSQL 下载与配置（Linux）

以下步骤以 Ubuntu / Debian 为例：

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

设置数据库账号和库（示例）：

```bash
sudo -u postgres psql
```

在 `psql` 中执行：

```sql
ALTER USER postgres WITH PASSWORD 'your_database_password_here';
CREATE DATABASE cognion_db;
\q
```

本机连接测试：

```bash
psql -U postgres -h 127.0.0.1 -d cognion_db
```

> 如使用 macOS / Windows，请按官方安装器安装 PostgreSQL，并保持连接参数与 `.env` 一致。

## .env 配置

后端读取 `backend/.env`（可由 `backend/.env.example` 复制）。

```bash
cd backend
cp .env.example .env
```

推荐最小配置：

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4.1-mini
OPENAI_URL=https://api.openai.com/v1

# 二选一：优先使用 DATABASE_URL
# DATABASE_URL=postgresql+psycopg2://postgres:your_password@127.0.0.1:5432/cognion_db

DATABASE_USER=postgres
DATABASE_PASSWORD=your_database_password_here
DATABASE_HOST=127.0.0.1
DATABASE_PORT=5432
DATABASE_NAME=cognion_db

PDF_STORAGE_DIR=./storage/papers
```

说明：

- 未配置 `OPENAI_API_KEY` 时，问答会返回占位响应（便于本地联调）
- `DATABASE_URL` 与分项配置同时存在时，通常优先使用 `DATABASE_URL`
- `PDF_STORAGE_DIR` 为 PDF 文件落盘根目录

## 启动方式

### 1) 启动后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

后端地址：`http://127.0.0.1:8000`

### 2) 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端地址：`http://127.0.0.1:5173`

## 主要 API（当前）

- `POST /api/papers/upload` 上传论文
- `GET /api/papers` 按目录查询论文
- `GET /api/papers/{paper_id}/file` 下载论文文件
- `PATCH /api/papers/{paper_id}/move` 移动论文目录
- `DELETE /api/papers/{paper_id}` 删除论文
- `GET /api/papers/{paper_id}/messages` 获取论文聊天历史
- `GET /api/folders/tree` 获取目录树
- `POST /api/folders` 创建文件夹
- `PATCH /api/folders/{folder_id}/move` 移动文件夹
- `PATCH /api/folders/{folder_id}/rename` 重命名文件夹
- `DELETE /api/folders/{folder_id}` 删除文件夹
- `POST /api/ask` 引用问答

## 项目 TODO List

- [ ]  添加对话 session 模块
- [ ]  考虑如何插入思路引导
- [ ]  笔记卡片生成设计
- [ ]  知识图谱生成的机制设计
