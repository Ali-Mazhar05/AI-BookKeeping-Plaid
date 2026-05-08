import os
import pathlib


def _load_dotenv(path: pathlib.Path) -> None:
    """Minimal .env loader — real values win over test defaults."""
    if not path.exists():
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Only set if not already in the environment (so shell vars still win)
            if key not in os.environ:
                os.environ[key] = value


# Load real .env first so integration tests get live credentials
_load_dotenv(pathlib.Path(__file__).parent.parent / ".env")

# Fill in anything still missing so Settings() won't raise during unit tests
_TEST_DEFAULTS = {
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_KEY": "test-supabase-key",
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
    "PLAID_CLIENT_ID": "test-plaid-client-id",
    "PLAID_SECRET_SANDBOX": "test-plaid-secret",
    "PLAID_TOKEN_FERNET_KEY": "dGVzdC1mZXJuZXQta2V5LTMyYnl0ZXMhISEhISE=",
    "RC_CLIENT_ID": "test-rc-client-id",
    "RC_CLIENT_SECRET": "test-rc-secret",
    "RC_JWT": "test-rc-jwt",
    "RC_FROM_NUMBER": "+15550000000",
    "SMS_RECIPIENT": "+15551111111",
    "EMAIL_RECIPIENT": "test@example.com",
    "GMAIL_CLIENT_ID": "test-gmail-client-id",
    "GMAIL_CLIENT_SECRET": "test-gmail-secret",
    "GMAIL_REFRESH_TOKEN": "test-gmail-refresh-token",
    "DASHBOARD_URL": "http://localhost:5173",
}

for key, value in _TEST_DEFAULTS.items():
    os.environ.setdefault(key, value)
