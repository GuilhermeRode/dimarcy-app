import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dimarcy.db"
    secret_key: str = "change-this-key"
    token_expire_minutes: int = 720
    cors_origins: str = "*"
    frontend_url: str = "https://app.dimarcy.com.br"  # used to build the password-reset link
    admin_email: str = "admin@dimarcy.com.br"
    admin_password: str = "admin123"
    enable_docs: bool = False  # /docs and /openapi.json map every route; keep off in production

    # E-mail notifications (order created, order delivered), sent via Resend's HTTP API.
    # Leave resend_api_key empty to disable sending.
    resend_api_key: str = ""
    mail_from: str = ""  # must be on a domain verified in Resend, e.g. "Di Marcy <pedidos@dimarcy.com.br>"
    notify_email: str = ""  # who receives it; defaults to admin_email when empty


settings = Settings()

# A known SECRET_KEY lets anyone forge login tokens. Without a real one, use a random key:
# safe, but everyone is logged out whenever the backend restarts.
if settings.secret_key in ("change-this-key", "troque-por-uma-chave-longa-e-aleatoria") or len(settings.secret_key) < 32:
    print("[config] SECRET_KEY missing or weak - using a random key. Set a 32+ char SECRET_KEY in .env.")
    settings.secret_key = secrets.token_urlsafe(48)

# Render/Heroku provide "postgres://", SQLAlchemy requires "postgresql://"
if settings.database_url.startswith("postgres://"):
    settings.database_url = settings.database_url.replace("postgres://", "postgresql://", 1)
