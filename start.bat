@echo off
chcp 65001 >nul
title 大内密探 - 企业情报分析系统
echo ==============================
echo   大内密探 - 启动中...
echo ==============================
echo.

:: 检查后端虚拟环境
if not exist "backend\.venv" if not exist "backend\venv" (
    echo [1/3] 创建 Python 虚拟环境...
    cd backend
    python -m venv .venv
    call .venv\Scripts\activate
    pip install -r requirements.txt
    cd ..
)

:: 安装前端依赖
if not exist "frontend\node_modules" (
    echo [2/3] 安装前端依赖...
    cd frontend
    call npm install
    cd ..
)

echo [3/3] 启动服务...

:: 启动后端
start "backend" cmd /c "cd backend && .venv\Scripts\uvicorn main:app --host 0.0.0.0 --port 8000"

:: 等后端先启动
timeout /t 3 /nobreak >nul

:: 启动前端
start "frontend" cmd /c "cd frontend && npx vite --host 0.0.0.0 --port 5173"

echo.
echo ==============================
echo   系统启动完成!
echo   后端: http://localhost:8000
echo   前端: http://localhost:5173
echo   API文档: http://localhost:8000/docs
echo ==============================
echo.
pause
