# Cognion

>Turn paper reading into knowledge growth.
>
>让论文阅读从信息获取，变成知识生长。

**如何让用户真正知道自己读到了什么，并把这些知识持续沉淀到自己的研究脉络中。**

现有的 AI 读论文工具，大多聚焦于单篇论文的总结、翻译、问答和结构解析。它们能提升信息获取效率，却很难解决阅读之后真正的断层：

- 读完了，但很难说清自己到底学到了什么
- 新知识没有和已有知识、研究方向形成连接
- 笔记难以坚持，读过的内容很快失去可复用价值

Cognion 希望解决的，正是这个问题。
我们希望把论文阅读从一次性的内容消费，变成一个持续外化理解、连接知识、激发科研想法的过程。

## Why Cognion?

研究者在读论文时，常常会遇到几个很普遍的问题：

### 1.阅读结果难以外化

很多时候，用户对论文只有一种“好像懂了”的模糊感觉。
但过几天回头再看，就会发现自己并没有形成清晰、稳定、可复述的理解。

### 2.知识积累是割裂的

一篇论文中的方法、假设、实验结论，很容易作为孤立的信息存在。
它们没有很好地进入用户自己的知识体系，也难以和当前研究问题发生联系。

### 3.笔记过程太重，难以持续

传统笔记依赖单向输出，成本高、反馈弱、容易疲惫。
很多人知道自己应该记笔记，但很难长期坚持，更难从笔记中持续获益。

### 4.现有工具更像“替你读”，而不是“帮你思考”

一些系统强调自动总结、多论文整合、Deep Research，但它们往往倾向于把人从思考环节中拿掉。
而我们认为，科研中真正有价值的部分，恰恰来自人的理解、怀疑、联想和迁移。

## What Cognion does

Cognion 的核心目标不是替用户完成阅读，而是：

> 让 AI 成为研究者的认知放大器，而不是认知替代物。

它主要围绕两个方向展开：

### 1. 面向阅读过程的思考陪伴

Cognion 会基于用户与模型的对话、提问方式、困惑点和表达习惯，逐步感知用户的：

- 知识背景
- 理解水平
- 认知偏好
- 思考风格

在此基础上，系统不会只给出“答案”，而是通过更有针对性的启发式提问、苏格拉底式追问，帮助用户更快进入思考状态，在阅读过程中完成理解、修正和深化。

对于那些更习惯通过“对话输出”来进行思考，而不是通过传统笔记来记录的人，这种方式会更加自然，也更容易坚持。

### 2. 面向长期积累的知识沉淀

Cognion 不希望阅读对话在结束后就消失。
相反，这些对话中产生的理解、问题、联想和判断，会被逐步组织为用户的个人知识结构。

这些沉淀可以进一步支持：

- 个性化论文推荐
- 背景知识补全
- 跨论文、跨领域知识连接
- 研究问题延展
- 新的 research idea 激发

也就是说，用户每读完一篇论文，不只是多了一次阅读记录，而是让自己的知识版图获得了一次可见的扩展。

## Core Ideas

Cognion 建立在几个核心理念之上：

### Thinking-first, not summary-first

相比“自动生成笔记”或“快速给出总结”，Cognion 更关注用户是否真的发生了思考。
系统的重点不是替你写结论，而是帮助你形成结论。

### Knowledge should be connected

知识不应该以孤立片段的形式堆积。
一篇论文中的新概念、新方法和新启发，应该能与用户已有的知识背景、研究问题和长期目标建立连接。

### Reading should leave cognitive traces

有价值的阅读，不只是看过内容，而是留下理解变化的轨迹。
从“不懂”，到“初步理解”，再到“能够联系自己的研究去判断其意义”，这是 Cognion 想帮助用户外化的核心过程。

### AI should keep humans in the loop

我们不希望 AI 取代科研阅读中的人类思考，而是希望它帮助研究者更持续、更深入、更有结构地思考。

## Key Features

### Interactive paper reading

在阅读论文时，用户可以随时与系统围绕某一段内容进行对话，而不是停留在静态高亮或纯问答模式。

### Socratic-style guidance

系统会根据用户的理解状态和知识背景，提出更有针对性的追问，帮助用户澄清概念、发现盲点、建立联系。

### Knowledge externalization

阅读过程中的理解、困惑、判断与联想，不会只是临时对话，而会逐步沉淀为可复用的知识资产。

### Personal knowledge graph

系统尝试把用户长期阅读中的知识点、研究兴趣、理解路径和问题意识组织成可扩展的个人知识图谱。

### Research-oriented reuse

这些积累不仅用于“回顾”，更用于未来的科研工作，比如论文推荐、知识补全、方向探索和 idea 生成。

## Our Vision

Cognion 希望成为一个真正服务于研究者长期成长的系统。

它不只是帮你更快读完论文，
而是帮你：

- 更清楚地知道自己学到了什么
- 更自然地把阅读过程转化为思考过程
- 更持续地积累属于自己的知识结构
- 更容易把新知识连接到自己的研究问题上

我们相信，真正有价值的科研阅读，不是“读过了”，而是：

> 新的知识被纳入了自己的认知系统，并开始与已有知识发生反应。

Cognion 想做的，就是帮助这个过程发生。

## 项目结构

- `frontend/`: React + Vite 前端
- `backend/`: FastAPI + SQLAlchemy 后端

## 当前功能（已实现）

### 前端

- 文献库支持多层级文件夹树，支持文件夹/论文的创建、重命名、删除与移动
- 阅读区支持 PDF 渲染、缩放、页码导航、文本选择与引用
- AI 对话支持流式回复、引用上下文问答、多会话创建/重命名/删除
- 右侧对话区支持 Markdown / 数学公式 / 代码高亮渲染
- 笔记区支持笔记 CRUD、笔记文件夹树与关联论文/会话管理

### 后端

- 上传 PDF 后保存文件并入库论文元信息
- 论文元信息持久化到 PostgreSQL（标题、作者、期刊、摘要等）
- 论文与目录关系持久化（支持移动后同步文件路径）
- 文件夹树接口返回层级结构与“是否含论文”聚合状态
- 对话消息按 `paper_id` + `session_id` 持久化并可回放，支持会话 CRUD
- LLM 问答支持流式返回，并支持引用片段上下文
- 笔记模块支持笔记 CRUD、笔记文件夹树、关联论文/会话
- 支持从会话中自动提炼并生成主题笔记

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

MINERU_ENABLED=false
MINERU_API_URL=
MINERU_API_KEY=
MINERU_MODEL=vlm
MINERU_TIMEOUT_SECONDS=180
MINERU_POLL_INTERVAL_SECONDS=3
MINERU_MAX_CHARS=100000

ALIYUN_OSS_ENABLED=false
ALIYUN_OSS_ENDPOINT=
ALIYUN_OSS_BUCKET=
ALIYUN_OSS_ACCESS_KEY_ID=
ALIYUN_OSS_ACCESS_KEY_SECRET=
ALIYUN_OSS_KEY_PREFIX=cognion/mineru
ALIYUN_OSS_PUBLIC_BASE_URL=
ALIYUN_OSS_SIGNED_URL_EXPIRES_SECONDS=900
```

说明：

- 未配置 `OPENAI_API_KEY` 时，问答会返回占位响应（便于本地联调）
- `DATABASE_URL` 与分项配置同时存在时，通常优先使用 `DATABASE_URL`
- `PDF_STORAGE_DIR` 为 PDF 文件落盘根目录
- 开启 `MINERU_ENABLED=true` 后，问答链路会走“上传 OSS → MinerU API 解析 PDF URL”
- `ALIYUN_OSS_ENDPOINT` 必须填写地域 Endpoint（例如 `https://oss-cn-shanghai.aliyuncs.com/`），不要填写带 Bucket 的域名（例如 `https://cognion.oss-cn-shanghai.aliyuncs.com/`）
- MinerU 返回的 Markdown 会缓存到与论文原件同路径、同名 `.md` 文件，后续优先读缓存避免重复解析

## OSS + MinerU 简单配置教程

下面这套是最小可用流程，按顺序做即可。

### 1) 准备账号与密钥

- 阿里云 OSS：准备 Bucket、`AccessKeyId`、`AccessKeySecret`
- MinerU：在官网 API 管理页生成 Token（填到 `MINERU_API_KEY`）

### 2) 确认 OSS 基本信息

- `ALIYUN_OSS_BUCKET`：你的 Bucket 名称（例如 `cognion`）
- `ALIYUN_OSS_ENDPOINT`：地域 Endpoint（例如 `https://oss-cn-shanghai.aliyuncs.com/`）

注意：

- `ALIYUN_OSS_ENDPOINT` 不要写成 `https://<bucket>.oss-xxx.aliyuncs.com/`
- Bucket 域名如果要用于对外访问，放在 `ALIYUN_OSS_PUBLIC_BASE_URL`

### 3) 在 `backend/.env` 填写配置

```env
MINERU_ENABLED=true
MINERU_API_URL=https://mineru.net/api/v4/extract/task
MINERU_API_KEY=your_mineru_token
MINERU_MODEL=vlm
MINERU_TIMEOUT_SECONDS=180
MINERU_POLL_INTERVAL_SECONDS=3
MINERU_MAX_CHARS=100000

ALIYUN_OSS_ENABLED=true
ALIYUN_OSS_ENDPOINT=https://oss-cn-shanghai.aliyuncs.com/
ALIYUN_OSS_BUCKET=your_bucket
ALIYUN_OSS_ACCESS_KEY_ID=your_access_key_id
ALIYUN_OSS_ACCESS_KEY_SECRET=your_access_key_secret
ALIYUN_OSS_KEY_PREFIX=cognion/mineru
ALIYUN_OSS_PUBLIC_BASE_URL=https://your_bucket.oss-cn-shanghai.aliyuncs.com/
ALIYUN_OSS_SIGNED_URL_EXPIRES_SECONDS=900
```

### 4) 启动后端并做一次链路验证

```bash
cd backend
uv sync
uv run python test/test_oss_mineru.py
```

如果成功，日志会看到：

- `[OK] OSS upload succeeded.`
- `[OK] MinerU API succeeded.`

### 5) 常见问题快速排查

- 报 `SSL: CERTIFICATE_VERIFY_FAILED` 且主机像 `bucket.bucket.oss-...`：
  `ALIYUN_OSS_ENDPOINT` 配错成了带 bucket 的域名，改为地域 Endpoint。
- MinerU 一直超时：
  先增大 `MINERU_TIMEOUT_SECONDS`（例如 300），确认目标 PDF 可公网访问。
- 返回文本很短或为空：
  检查 `MINERU_MODEL`（建议 `vlm`）、以及 MinerU 任务状态是否 `done`。

## 启动方式

### 1) 启动后端

```bash
cd backend
uv sync
cp .env.example .env
uv run uvicorn app.main:app --reload --port 8000
```

后端地址：`http://127.0.0.1:8000`

### 2) 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端地址：`http://127.0.0.1:5173`

## 项目 TODO List

- [x]  添加对话 session 模块
- [x]  考虑如何插入思路引导
- [x]  笔记卡片生成设计
- [ ]  知识图谱生成的机制设计
