"""鉴权路由——用户名即身份（无密码轻量登录）"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import User
from schemas import LoginRequest, LoginResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["鉴权"])


@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """登录：用户名不存在则自动创建（用户名即账号，无密码）。"""
    username = (data.username or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="用户名不能为空")

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        user = User(username=username)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info(f"新用户注册: {username}")
    return LoginResponse(username=user.username, user_id=user.id)
