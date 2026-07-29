"""系统配置路由（按用户隔离：每用户私有 LLM / 搜索引擎配置）"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from deps import get_current_user, DEFAULT_USER_SETTINGS
from models import UserConfig, User
from schemas import SystemConfigOut, SystemConfigUpdate, SystemConfigItem

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["系统配置"])


@router.get("", response_model=SystemConfigOut)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的私有配置（未设置的键回落到默认值）"""
    result = await db.execute(
        select(UserConfig).where(UserConfig.user_id == current_user.id)
    )
    rows = result.scalars().all()
    db_map = {r.key: r.value for r in rows}

    merged = {}
    for key, default in DEFAULT_USER_SETTINGS.items():
        merged[key] = db_map.get(key, default)

    return SystemConfigOut(
        items=[SystemConfigItem(key=k, value=v) for k, v in merged.items()]
    )


@router.put("", response_model=SystemConfigOut)
async def update_settings(
    data: SystemConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量更新当前用户的私有配置"""
    for item in data.items:
        result = await db.execute(
            select(UserConfig).where(
                UserConfig.user_id == current_user.id,
                UserConfig.key == item.key,
            )
        )
        row = result.scalar_one_or_none()
        if row:
            row.value = item.value
            row.updated_at = datetime.now(timezone.utc)
        else:
            db.add(UserConfig(user_id=current_user.id, key=item.key, value=item.value))

    await db.commit()
    logger.info(f"用户 {current_user.username} 更新了私有配置: {[it.key for it in data.items]}")
    return await get_settings(db, current_user)
