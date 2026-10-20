
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr


class Settings(BaseSettings):
    app_name: str = "In4-Backend"
    environment: str = "development"
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/in4_db"
    jwt_secret_key: SecretStr | None = None
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    refresh_token_days: int = 7
    supabase_url: str | None = None
    supabase_secret_key: SecretStr | None = None
    supabase_service_role_key: SecretStr | None = None
    supabase_profile_bucket: str = "profile-image"
    supabase_article_bucket: str = "avatars_uploads"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
