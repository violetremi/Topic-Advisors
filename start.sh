#!/bin/bash
# 大内密探 - 企业情报分析系统 启动脚本

echo "=============================="
echo "  大内密探 - 启动中..."
echo "=============================="

# 检查后端虚拟环境
if [ ! -d "backend/.venv" ] && [ ! -d "backend/venv" ]; then
    echo "[1/3] 创建 Python 虚拟环境..."
    cd backend && python -m venv .venv && source .venv/Scripts/activate && pip install -r requirements.txt && cd ..
fi

# 激活虚拟环境
if [ -d "backend/.venv" ]; then
    source backend/.venv/Scripts/activate
elif [ -d "backend/venv" ]; then
    source backend/venv/Scripts/activate
fi

echo "[1/3] 后端虚拟环境就绪 ✓"

# 安装前端依赖
if [ ! -d "frontend/node_modules" ]; then
    echo "[2/3] 安装前端依赖..."
    cd frontend && npm install && cd ..
fi
echo "[2/3] 前端依赖就绪 ✓"

# 启动后端（后台）
echo "[3/3] 启动服务..."
cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# 启动前端
cd frontend && npx vite --host 0.0.0.0 --port 5173 &
FRONTEND_PID=$!

echo ""
echo "=============================="
echo "  系统启动完成!"
echo "  后端: http://localhost:8000"
echo "  前端: http://localhost:5173"
echo "  API文档: http://localhost:8000/docs"
echo "=============================="
echo "  按 Ctrl+C 停止所有服务"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM
wait
