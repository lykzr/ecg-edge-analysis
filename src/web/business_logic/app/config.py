# FastAPI 配置

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 数据库
    DATABASE_URL: str = "sqlite:///./ecg_health.db"

    # JWT
    SECRET_KEY: str = "change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # AI 模型
    AI_MODEL_PATH: str = "./ai_model/models"
    AI_TIMEOUT: int = 5

    # 存储
    DATA_STORAGE_PATH: str = "./data/raw"

    class Config:
        env_file = ".env"

settings = Settings()
