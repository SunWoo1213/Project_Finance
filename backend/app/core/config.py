from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"

class Settings(BaseSettings):
    PROJECT_NAME: str
    API_V1_STR: str
    DATABASE_URL: str
    OPENAI_API_KEY: str | None = None
    ALPHA_VANTAGE_API_KEY: str | None = None
    FRED_API_KEY: str | None = None
    ECOS_API_KEY: str | None = None
    
    # JWT Authentication
    SECRET_KEY: str = "a_very_secure_randomly_generated_string_like_9b0d2a8"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    model_config = SettingsConfigDict(
        env_file=str(ROOT_ENV_FILE),
        extra="ignore",
    )

settings = Settings()
