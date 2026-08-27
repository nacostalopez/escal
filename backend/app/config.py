from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://escal:escal@localhost:5432/escal"

    class Config:
        env_file = ".env"


settings = Settings()
