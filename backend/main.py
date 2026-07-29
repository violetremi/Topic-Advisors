"""
大内密探 - 企业情报分析系统
FastAPI 后端入口
"""
import logging
import os
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from database import init_db
from deps import get_current_user
from routers import companies, persons, reports, settings, news, person_analysis, topic_chain, auth

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("--- 大内密探 系统启动 ---")
    await init_db()
    logger.info("数据库初始化完成")
    yield
    logger.info("--- 系统关闭 ---")


app = FastAPI(
    title="大内密探 - 企业情报分析系统",
    description="前后端分离的企业情报分析 B 端系统",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS - 生产环境由后端同源托管前端，这里放宽以兼容自定义域名/反向代理
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由（业务路由统一要求登录：从 X-Username 头解析当前用户）
_AUTH = [Depends(get_current_user)]
app.include_router(companies.router, dependencies=_AUTH)
app.include_router(persons.router, dependencies=_AUTH)
app.include_router(reports.router, dependencies=_AUTH)
app.include_router(settings.router, dependencies=_AUTH)
app.include_router(news.router, dependencies=_AUTH)
app.include_router(person_analysis.router, dependencies=_AUTH)
app.include_router(topic_chain.router, dependencies=_AUTH)
# 登录接口本身不要求鉴权
app.include_router(auth.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """捕获未处理异常，避免客户端只看到无信息的 Internal Server Error。"""
    tb = traceback.format_exc()
    logger.error("未处理异常 %s %s: %s\n%s", request.method, request.url.path, exc, tb)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc) or "服务器内部错误"},
    )


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "大内密探"}


# ---------------------------------------------------------------------------
# 生产环境：由后端直接托管打包后的前端（frontend/dist）
# 开发环境（vite dev server）不触发此分支，前后端分离仍可独立运行
# ---------------------------------------------------------------------------
_FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    # 以 /api 开头的路径不属于前端路由，交给异常处理返回 404
    if full_path.startswith("api"):
        raise HTTPException(status_code=404, detail="Not Found")
    # 仅当构建产物存在时启用静态托管
    if os.path.isdir(_FRONTEND_DIST):
        requested = os.path.join(_FRONTEND_DIST, full_path)
        if full_path and os.path.isfile(requested):
            return FileResponse(requested)
        # SPA 兜底：未匹配到静态资源时返回 index.html
        return FileResponse(os.path.join(_FRONTEND_DIST, "index.html"))
    # 未构建前端时给出提示（开发期直接用 vite 即可）
    return {"detail": "前端尚未构建，请运行 npm run build 或启动 vite dev server"}
