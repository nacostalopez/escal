from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://escal:escal@localhost:5432/escal"

    jwt_secret: str = "dev-only-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Fernet key for encrypting store_credentials at rest. Dev-only default —
    # generate a real one with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    credentials_encryption_key: str = "Qxsu0Kb675R0dWY-WeAE-1hvcXLTQj74_pJrlsr_kG4="

    class Config:
        env_file = ".env"


settings = Settings()
