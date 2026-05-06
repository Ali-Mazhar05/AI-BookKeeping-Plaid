import jwt
from fastapi import Request, HTTPException
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from .client import get_plaid_client
from .sync import sync_account
# from ..notifier.dispatch import send_notification # To be implemented in M9

logger = structlog.get_logger()
client = get_plaid_client()

import hashlib
import hmac
import jwt
import zlib
import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from plaid.model.webhook_verification_key_get_request import WebhookVerificationKeyGetRequest

# Key cache to avoid fetching JWKS on every request
KEY_CACHE = {}

def jwk_to_pem(jwk):
    """Converts an ES256 JWK to PEM format for PyJWT/cryptography."""
    x = base64.urlsafe_b64decode(jwk['x'] + '==')
    y = base64.urlsafe_b64decode(jwk['y'] + '==')
    public_key = ec.EllipticCurvePublicNumbers(
        int.from_bytes(x, 'big'),
        int.from_bytes(y, 'big'),
        ec.SECP256R1()
    ).public_key()
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

async def verify_webhook_signature(request: Request) -> bool:
    """
    Verifies Plaid webhook signature using JWKS.
    See: https://plaid.com/docs/api/webhooks/#webhook-verification
    """
    plaid_verification = request.headers.get("Plaid-Verification")
    if not plaid_verification:
        logger.warning("Missing Plaid-Verification header")
        return False

    try:
        # 1. Get raw request body
        body = await request.body()
        
        # 2. Extract kid from JWT header
        unverified_header = jwt.get_unverified_header(plaid_verification)
        kid = unverified_header.get("kid")
        if not kid:
            logger.warning("Plaid-Verification JWT missing 'kid'")
            return False
            
        # 3. Retrieve public key from Plaid (with local caching)
        if kid not in KEY_CACHE:
            key_request = WebhookVerificationKeyGetRequest(key_id=kid)
            # plaid-python is synchronous
            key_response = client.webhook_verification_key_get(key_request)
            KEY_CACHE[kid] = jwk_to_pem(key_response['key'])
            
        public_key_pem = KEY_CACHE[kid]
        
        # 4. Verify JWT signature and expiration (iat must be within last 5 mins)
        claims = jwt.decode(
            plaid_verification, 
            public_key_pem, 
            algorithms=["ES256"],
            options={"verify_iat": True, "leeway": 300} # 5 min tolerance
        )
        
        # 5. Verify body integrity
        request_body_sha256 = claims.get("request_body_sha256")
        computed_hash = hashlib.sha256(body).hexdigest()
        
        if not hmac.compare_digest(computed_hash, request_body_sha256):
            logger.error("Webhook body hash mismatch")
            return False
            
        return True

    except Exception as e:
        logger.error("Webhook signature verification failed", error=str(e))
        return False

async def handle_webhook(session: AsyncSession, payload: dict):
    webhook_type = payload.get("webhook_type")
    webhook_code = payload.get("webhook_code")
    item_id = payload.get("item_id")
    
    if webhook_type != "TRANSACTIONS":
        logger.info("Ignoring non-transactions webhook", type=webhook_type)
        return
        
    logger.info("Received Plaid webhook", code=webhook_code, item_id=item_id)
    
    # 1. Look up the bank_account_id for this item_id
    result = await session.execute(
        text("SELECT id, entity_id FROM bank_accounts WHERE plaid_item_id = :item_id"),
        {"item_id": item_id}
    )
    account = result.fetchone()
    if not account:
        logger.warning("Webhook for unknown item_id", item_id=item_id)
        return
        
    account_id = account.id
    entity_id = account.entity_id

    # 2. Handle codes
    if webhook_code in ("INITIAL_UPDATE", "HISTORICAL_UPDATE", "DEFAULT_UPDATE", "SYNC_UPDATES_AVAILABLE"):
        # We must trigger sync async. We shouldn't block the webhook response.
        # In a real system, we'd enqueue a task to APScheduler or Celery.
        # For now, we will assume APScheduler can be triggered, or we do it inline if quick.
        import asyncio
        asyncio.create_task(sync_account(account_id))
        
    elif webhook_code == "ITEM_LOGIN_REQUIRED":
        logger.error("ITEM_LOGIN_REQUIRED", item_id=item_id)
        # Update bank_account status
        await session.execute(
            text("UPDATE bank_accounts SET plaid_last_error = 'ITEM_LOGIN_REQUIRED' WHERE id = :id"),
            {"id": account_id}
        )
        await session.commit()
        # await send_notification(entity_id, type='reauth_required', channel='both', context={})
        
    elif webhook_code == "USER_PERMISSION_REVOKED":
        logger.error("USER_PERMISSION_REVOKED", item_id=item_id)
        await session.execute(
            text("UPDATE bank_accounts SET is_active = FALSE WHERE id = :id"),
            {"id": account_id}
        )
        await session.commit()
        # await send_notification(entity_id, type='permission_revoked', channel='both', context={})
        
    elif webhook_code == "PENDING_EXPIRATION":
        logger.warning("PENDING_EXPIRATION", item_id=item_id)
        # await send_notification(entity_id, type='pending_expiration', channel='email', context={})
