"""系统配置路由（运行时持久化，无需重启生效）"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import SystemConfig
from schemas import SystemConfigOut, SystemConfigUpdate, SystemConfigItem

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["系统配置"])

# 默认配置（首次初始化时写入 DB）
DEFAULT_SETTINGS = {
    "llm_base_url": "",
    "llm_api_key": "",
    "llm_model": "",
    "search_provider": "tavily",
    "search_api_key": "",
    "tavily_api_key": "",
}


@router.get("", response_model=SystemConfigOut)
async def get_settings(db: AsyncSession = Depends(get_db)):
    """获取所有系统配置"""
    result = await db.execute(select(SystemConfig))
    rows = result.scalars().all()
    db_map = {r.key: r.value for r in rows}

    # 合并默认值：DB 中已有的用 DB 值，没有的用默认值
    merged = {}
    for key, default in DEFAULT_SETTINGS.items():
        merged[key] = db_map.get(key, default)

    return SystemConfigOut(items=[SystemConfigItem(key=k, value=v) for k, v in merged.items()])


@router.put("", response_model=SystemConfigOut)
async def update_settings(data: SystemConfigUpdate, db: AsyncSession = Depends(get_db)):
    """批量更新系统配置"""
    for item in data.items:
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.key == item.key)
        )
        row = result.scalar_one_or_none()
        if row:
            row.value = item.value
            row.updated_at = datetime.now(timezone.utc)
        else:
            db.add(SystemConfig(key=item.key, value=item.value))

    await db.commit()
    logger.info(f"系统配置已更新: {[it.key for it in data.items]}")
    return await get_settings(db)
