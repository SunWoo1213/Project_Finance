from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str
    API_V1_STR: str
    DATABASE_URL: str
    OPENAI_API_KEY: str | None = None

    class Config:
        env_file = ".env"

settings = Settings()
