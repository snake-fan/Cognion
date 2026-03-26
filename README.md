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
