from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dimarcy.db"
    secret_key: str = "change-this-key"
    token_expire_minutes: int = 720
    cors_origins: str = "*"
    admin_email: str = "admin@dimarcy.com.br"
    admin_password: str = "admin123"

    # E-mail notifications (order delivered), sent via Resend's HTTP API.
    # Leave resend_api_key empty to disable sending.
    resend_api_key: str = ""
    mail_from: str = ""  # must be on a domain verified in Resend, e.g. "Di Marcy <pedidos@dimarcy.com.br>"
    notify_email: str = ""  # who receives it; defaults to admin_email when empty


settings = Settings()

# Render/Heroku provide "postgres://", SQLAlchemy requires "postgresql://"
if settings.database_url.startswith("postgres://"):
    settings.database_url = settings.database_url.replace("postgres://", "postgresql://", 1)
