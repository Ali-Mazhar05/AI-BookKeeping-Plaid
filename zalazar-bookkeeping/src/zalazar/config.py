from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, PostgresDsn
from typing import Optional

class Settings(BaseSettings):
    # Supabase / Postgres
    SUPABASE_URL: str
    SUPABASE_KEY: SecretStr
    DATABASE_URL: str

    # Plaid
    PLAID_CLIENT_ID: str
    PLAID_SECRET_SANDBOX: SecretStr
    PLAID_SECRET_DEVELOPMENT: Optional[SecretStr] = None
    PLAID_SECRET_PRODUCTION: Optional[SecretStr] = None
    PLAID_ENV: str = "sandbox"

    # Encryption
    PLAID_TOKEN_FERNET_KEY: SecretStr

    # AI Providers
    GEMINI_API_KEY: Optional[SecretStr] = None
    OPENAI_API_KEY: Optional[SecretStr] = None
    ANTHROPIC_API_KEY: Optional[SecretStr] = None

    # Notifications
    # RingCentral Notifications
    RC_CLIENT_ID: str
    RC_CLIENT_SECRET: SecretStr
    RC_SERVER_URL: str = "https://platform.devtest.ringcentral.com"
    RC_JWT: SecretStr
    RC_FROM_NUMBER: str
    SMS_RECIPIENT: str
    EMAIL_RECIPIENT: str

    # Gmail API (OAuth)
    GMAIL_CLIENT_ID: str
    GMAIL_CLIENT_SECRET: SecretStr
    GMAIL_REFRESH_TOKEN: SecretStr

    # SMTP Settings (Fallback)
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[SecretStr] = None

    # App Settings
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "local"
    DASHBOARD_URL: str = "http://localhost:5173"
    API_URL: str = "http://localhost:8000"
    SENTRY_DSN: Optional[str] = None
    
    # Reconciliation
    RECONCILIATION_TOLERANCE: float = 0.01

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
