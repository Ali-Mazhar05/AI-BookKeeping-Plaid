import plaid
from plaid.api import plaid_api
from cryptography.fernet import Fernet
from ..config import settings

def get_plaid_client():
    configuration = plaid.Configuration(
        host=plaid.Environment.Sandbox if settings.PLAID_ENV == "sandbox" else 
             plaid.Environment.Development if settings.PLAID_ENV == "development" else 
             plaid.Environment.Production,
        api_key={
            'clientId': settings.PLAID_CLIENT_ID,
            'secret': settings.PLAID_SECRET_SANDBOX.get_secret_value() if settings.PLAID_ENV == "sandbox" else
                      settings.PLAID_SECRET_DEVELOPMENT.get_secret_value() if settings.PLAID_ENV == "development" else
                      settings.PLAID_SECRET_PRODUCTION.get_secret_value(),
        }
    )
    api_client = plaid.ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)

def encrypt_token(token: str) -> str:
    """Encrypts a Plaid access token using Fernet."""
    f = Fernet(settings.PLAID_TOKEN_FERNET_KEY.get_secret_value().encode())
    return f.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    """Decrypts a Plaid access token using Fernet."""
    f = Fernet(settings.PLAID_TOKEN_FERNET_KEY.get_secret_value().encode())
    return f.decrypt(encrypted_token.encode()).decode()
