# Cognion

Cognion is an AI-powered research reading system that goes beyond summarizing papers. Instead of treating documents as static content, Cognion models your evolving understanding—what you’ve grasped, where you’re confused, and how your knowledge grows over time. Cognion doesn’t just help you read papers—it helps you better thinking about them.

## 项目结构

- `frontend/`: React + Vite 前端
- `backend/`: FastAPI 后端

## 当前已实现（MVP）

1. 前端渲染 PDF（上传本地 PDF 后中间区域显示）
2. 鼠标选择 PDF 文本后，自动写入右侧对话栏“引用片段”
3. 输入提问后调用后端 `/api/ask`，后端将“问题 + 引用 + PDF内容节选”组合为上下文，调用大模型
4. IDE 风格布局：中间阅读区 + 左侧功能分类栏 + 右侧 AI 对话栏
5. 右侧 AI 栏支持拖拽缩放
6. 左右侧边栏均支持折叠

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

如需真实大模型回答，请在 `backend/.env` 中配置：

```env
OPENAI_API_KEY=你的key
OPENAI_MODEL=gpt-4.1-mini
```

未配置 key 时，后端会返回本地占位回复，便于先验证产品流程。

### 2) 启动前端

```bash
cd frontend
npm install
npm run dev
```

浏览器访问：`http://127.0.0.1:5173`

## 后续扩展建议

- 在左侧功能栏继续增加能力模块（如笔记整理、术语解释、知识图谱）
- 将 `frontend/src/App.jsx` 逐步拆分为模块化组件
- 在后端增加对话历史、RAG 检索与多模型路由
