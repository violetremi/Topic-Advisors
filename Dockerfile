# ---------------------------------------------------------------------------
# 多阶段构建：第一阶段用 Node 构建前端，第二阶段用 Python 运行后端
# 最终镜像同时包含打包后的前端(dist)与 FastAPI 后端，由后端同源托管
# Hugging Face Spaces (Docker SDK) 会自动构建并运行此镜像
# ---------------------------------------------------------------------------

# ---- 阶段 1：构建前端 ----
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ---- 阶段 2：运行后端 ----
FROM python:3.11-slim
WORKDIR /app

# 后端源码
COPY backend/ /app/backend/

# 从阶段 1 拷贝已构建的前端静态文件
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

WORKDIR /app/backend
RUN pip install --no-cache-dir -r requirements.txt

# HF Spaces 通过 $PORT 注入端口（默认 7860）
EXPOSE 7860
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860}"]
