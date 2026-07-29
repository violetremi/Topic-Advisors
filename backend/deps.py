"""鉴权依赖与运行时配置加载（多用户隔离核心）

- get_current_user: 从请求头 X-Username 解析当前用户，不存在则自动创建（用户名即身份，无密码）。
- get_user_llm_config: 读取当前用户的私有配置（LLM / 搜索引擎），缺省回落到 .env 与默认值。
- llm_config_kwargs: 将用户配置转为 call_llm / agent 的传参。
"""
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import User, UserConfig, Company
from config.settings import settings

logger = __import__("logging").getLogger(__name__)

# 每用户配置的默认键与默认值（同时也作为前端表单的字段来源）
DEFAULT_USER_SETTINGS = {
    "llm_base_url": "",
    "llm_api_key": "",
    "llm_model": "",
    "llm_embed_model": "",
    "search_provider": "tavily",
    "search_api_key": "",
    "tavily_api_key": "",
}


async def get_current_user(
    x_username: str | None = Header(default=None, alias="X-Username"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从请求头 X-Username 解析当前用户；用户名为空则 401；不存在则自动创建。

    注意：本系统采用「用户名即身份、无密码」的轻量鉴权，隔离的是用户之间的数据，
    并非真实安全防护——任何知道他人用户名的人都能进入其账号。
    """
    if not x_username or not x_username.strip():
        raise HTTPException(status_code=401, detail="未登录")
    username = x_username.strip()
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        user = User(username=username)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


async def get_owned_company(company_id: int, user: User, db: AsyncSession) -> Company:
    """获取企业并校验归属：不属于当前用户（或不存在）一律返回 404。"""
    company = await db.get(Company, company_id)
    if not company or company.user_id != user.id:
        raise HTTPException(status_code=404, detail="企业不存在")
    return company


async def get_user_llm_config(user: User, db: AsyncSession) -> dict:
    """读取当前用户的私有 LLM / 搜索配置，缺省回落到 .env 与默认值。"""
    result = await db.execute(select(UserConfig).where(UserConfig.user_id == user.id))
    rows = result.scalars().all()
    cfg = {r.key: r.value for r in rows}

    # 搜索引擎配置：兼容历史字段 tavily_api_key；DuckDuckGo 不可用时自动切到 Tavily
    search_provider = cfg.get("search_provider") or DEFAULT_USER_SETTINGS["search_provider"]
    search_api_key = cfg.get("search_api_key") or ""
    tavily_key = cfg.get("tavily_api_key") or ""
    if search_provider == "tavily" and not search_api_key and tavily_key:
        search_api_key = tavily_key
    elif search_provider == "duckduckgo" and tavily_key:
        search_provider = "tavily"
        search_api_key = tavily_key
        logger.info("检测到 tavily_api_key，自动切换搜索引擎为 Tavily")

    return {
        "base_url": cfg.get("llm_base_url") or settings.openai_base_url,
        "api_key": cfg.get("llm_api_key") or settings.openai_api_key,
        "model": cfg.get("llm_model") or settings.llm_model,
        "embed_model": cfg.get("llm_embed_model") or settings.embed_model,
        "search_provider": search_provider,
        "search_api_key": search_api_key,
    }


def llm_config_kwargs(cfg: dict) -> dict:
    """将用户配置转为 call_llm / 各 agent 的传参（含搜索配置，避免全局可变状态并发问题）。"""
    return {
        "base_url_override": cfg["base_url"],
        "api_key_override": cfg["api_key"],
        "model_override": cfg["model"],
        "search_provider": cfg.get("search_provider"),
        "search_api_key": cfg.get("search_api_key"),
    }
