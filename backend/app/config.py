from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dimarcy.db"
    secret_key: str = "change-this-key"
    token_expire_minutes: int = 720
    cors_origins: str = "*"
    admin_email: str = "admin@dimarcy.com.br"
    admin_password: str = "admin123"

    # E-mail notifications (order delivered). Leave smtp_host empty to disable sending.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    notify_email: str = ""  # defaults to admin_email when empty


settings = Settings()

# Render/Heroku provide "postgres://", SQLAlchemy requires "postgresql://"
if settings.database_url.startswith("postgres://"):
    settings.database_url = settings.database_url.replace("postgres://", "postgresql://", 1)
