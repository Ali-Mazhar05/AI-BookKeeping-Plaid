from typing import Optional, Dict, Any
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from .client import get_plaid_client, encrypt_token
from ..db import supabase
from ..config import settings
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.accounts_get_request import AccountsGetRequest

client = get_plaid_client()

class ExchangeTokenRequest(BaseModel):
    public_token: str
    metadata: Dict[str, Any]
    entity_id: str

async def create_link_token(entity_id: str, access_token: Optional[str] = None) -> str:
    params = {
        "products": [Products("transactions")] if not access_token else [], # Products must be empty for update mode
        "client_name": "Zalazar Holdings LLC",
        "country_codes": [CountryCode("US")],
        "language": "en",
        "user": LinkTokenCreateRequestUser(client_user_id=str(entity_id)),
        "webhook": f"{settings.SUPABASE_URL}/functions/v1/plaid-webhook"
    }
    
    if access_token:
        params["access_token"] = access_token

    request = LinkTokenCreateRequest(**params)
    response = client.link_token_create(request)
    return response['link_token']

async def exchange_public_token_and_save(session: AsyncSession, request_data: ExchangeTokenRequest) -> Dict[str, Any]:
    # 1. Exchange public token
    try:
        exchange_request = ItemPublicTokenExchangeRequest(
            public_token=request_data.public_token
        )
        exchange_response = client.item_public_token_exchange(exchange_request)
        access_token = exchange_response['access_token']
        item_id = exchange_response['item_id']
    except Exception as e:
        print(f"DEBUG: Plaid exchange failed: {str(e)}")
        raise

    # 2. Encrypt access token
    encrypted_token = encrypt_token(access_token)

    # 3. Fetch account metadata
    try:
        accounts_request = AccountsGetRequest(access_token=access_token)
        accounts_response = client.accounts_get(accounts_request)
    except Exception as e:
        print(f"DEBUG: Plaid accounts fetch failed: {str(e)}")
        raise

    # 4. Upsert bank_accounts
    for account in accounts_response['accounts']:
        # Map Plaid account type to our check values.
        # ('checking','savings','credit','paypal','loan','other')
        account_type_map = {
            'depository': 'checking',
            'credit': 'credit',
            'loan': 'loan',
            'investment': 'other',
            'other': 'other'
        }
        mapped_type = account_type_map.get(str(account.type), 'other')
        if mapped_type == 'checking' and str(account.subtype) == 'savings':
            mapped_type = 'savings'

        institution_name = request_data.metadata.get('institution', {}).get('name', 'Unknown Institution')
        
        # Get balance if available
        current_balance = getattr(account.balances, 'current', None)

        try:
            await session.execute(text("""
                INSERT INTO bank_accounts (
                    entity_id,
                    plaid_account_id,
                    plaid_item_id,
                    plaid_access_token_encrypted,
                    bank_name,
                    account_name,
                    account_last4,
                    account_type,
                    current_balance,
                    is_active,
                    last_synced_at,
                    updated_at
                ) VALUES (
                    :entity_id, :plaid_account_id, :plaid_item_id, :encrypted_token,
                    :bank_name, :account_name, :account_last4, :account_type,
                    :current_balance, TRUE, NOW(), NOW()
                )
                ON CONFLICT (plaid_account_id) DO UPDATE SET
                    plaid_access_token_encrypted = EXCLUDED.plaid_access_token_encrypted,
                    current_balance = EXCLUDED.current_balance,
                    is_active = TRUE,
                    last_synced_at = NOW(),
                    updated_at = NOW()
            """), {
                "entity_id": request_data.entity_id,
                "plaid_account_id": account.account_id,
                "plaid_item_id": item_id,
                "encrypted_token": encrypted_token,
                "bank_name": institution_name,
                "account_name": account.name,
                "account_last4": account.mask,
                "account_type": mapped_type,
                "current_balance": current_balance
            })

        except Exception as e:
            print(f"DEBUG: DB Upsert failed for account {account.account_id}: {str(e)}")
            raise

    # 5. Return safe info
    return {
        "item_id": item_id,
        "accounts": [
            {
                "account_id": a.account_id,
                "name": a.name,
                "mask": a.mask,
                "type": str(a.type),
                "subtype": str(a.subtype)
            } for a in accounts_response['accounts']
        ],
        "institution": request_data.metadata.get('institution')
    }

