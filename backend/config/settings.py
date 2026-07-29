"""应用配置"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # LLM
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o"
    # Embeddings（默认对接 LM Studio 的 bge-m3）
    embed_model: str = "text-embedding-bge-m3"

    # Database
    database_url: str = "sqlite+aiosqlite:///./intel_agent.db"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
