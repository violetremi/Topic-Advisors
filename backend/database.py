"""数据库连接与会话管理"""
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool, StaticPool
from config.settings import settings

logger = logging.getLogger(__name__)

_db_url = settings.database_url
_engine_kwargs: dict = {"echo": False}
# SQLite：并发请求下用 StaticPool，避免默认连接池在回滚后取连接触发 MissingGreenlet
if _db_url.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    # :memory: 必须 StaticPool；文件库用 NullPool 也可安全支持多并发
    if ":memory:" in _db_url:
        _engine_kwargs["poolclass"] = StaticPool
    else:
        _engine_kwargs["poolclass"] = NullPool

engine = create_async_engine(_db_url, **_engine_kwargs)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        from models import Company, Person, Report, CheckRun, PersonAnalysis, TopicChain, News  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)

        # 增量迁移（在同一个连接中执行，避免 MissingGreenlet）
        _migrate = [
            "ALTER TABLE persons ADD COLUMN hobbies TEXT DEFAULT ''",
            "ALTER TABLE reports ADD COLUMN batch_id VARCHAR(36) DEFAULT NULL",
            "ALTER TABLE check_runs ADD COLUMN batch_id VARCHAR(36) DEFAULT ''",
            "ALTER TABLE news ADD COLUMN embedding TEXT DEFAULT ''",
            "ALTER TABLE companies ADD COLUMN user_id INTEGER REFERENCES users(id)",
        ]
        for sql in _migrate:
            try:
                await conn.execute(text(sql))
            except Exception:
                pass  # 字段已存在则忽略

        # 重建索引（忽略已存在）
        try:
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_news_company_type_created "
                "ON news (company_id, news_type, created_at)"
            ))
        except Exception:
            pass

        # 清理旧数据（仅首次迁移时）
        try:
            user_count = (await conn.execute(text("SELECT COUNT(*) FROM users"))).scalar() or 0
            if user_count == 0:
                await conn.execute(text("DELETE FROM companies"))
                logger.info("迁移：已清空升级前的存量业务数据（无归属用户）")
        except Exception:
            pass
