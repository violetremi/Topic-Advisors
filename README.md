# 🕵️ 大内密探 - 企业情报分析系统

前后端分离的企业情报分析 B 端系统，基于 AI 大模型驱动。

## 🚀 快速启动

### 方式一：Windows 一键启动（推荐）

```bash
双击 start.bat
```

脚本会自动安装依赖并启动前后端服务。

### 方式二：命令行启动

```bash
# 1. 后端
cd backend
python -m venv .venv
source .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 2. 前端（新开终端）
cd frontend
npm install
npx vite --host
```

### 方式三：Mac/Linux

```bash
chmod +x start.sh
./start.sh
```

## 🌐 访问地址

| 服务 | 地址 |
|------|------|
| 前端页面 | http://localhost:5173 |
| 后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |

## ⚙️ 首次使用配置

1. 打开前端页面 → 左侧菜单「系统管理」
2. 配置 AI 大模型：
   - **API 接口地址**: 例如 `http://127.0.0.1:1234/v1`（本地）或云服务地址
   - **API Key**: 你的 API Key（本地模型可不填）
   - **模型名称**: 例如 `gpt-4o`、`qwen2.5` 等
3. 点击「保存配置」
4. 可选：配置搜索引擎（系统管理 → 联网搜索引擎配置）

## 📦 技术栈

- **前端**: React + TypeScript + Ant Design + Vite
- **后端**: Python + FastAPI + SQLAlchemy + SQLite
- **AI**: 兼容 OpenAI API 格式的大模型（本地或云端）

## 📁 项目结构

```
├── backend/          # Python 后端
│   ├── routers/      # API 路由
│   ├── services/     # AI Agent 服务
│   ├── config/       # 配置与 Prompt
│   ├── models.py     # 数据库模型
│   └── main.py       # 入口
├── frontend/         # React 前端
│   └── src/
│       ├── pages/    # 页面组件
│       ├── components/ # 通用组件
│       └── api/      # API 调用层
└── start.sh          # 启动脚本
