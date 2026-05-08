import asyncio
import hashlib
import hmac
import base64
import jwt
import structlog
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from plaid.model.webhook_verification_key_get_request import WebhookVerificationKeyGetRequest
from .client import get_plaid_client
from .sync import sync_account
from ..notifier import dispatch

logger = structlog.get_logger()
client = get_plaid_client()

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
        body = await request.body()

        unverified_header = jwt.get_unverified_header(plaid_verification)
        kid = unverified_header.get("kid")
        if not kid:
            logger.warning("Plaid-Verification JWT missing 'kid'")
            return False

        if kid not in KEY_CACHE:
            key_request = WebhookVerificationKeyGetRequest(key_id=kid)
            key_response = client.webhook_verification_key_get(key_request)
            KEY_CACHE[kid] = jwk_to_pem(key_response['key'])

        public_key_pem = KEY_CACHE[kid]

        claims = jwt.decode(
            plaid_verification,
            public_key_pem,
            algorithms=["ES256"],
            options={"verify_iat": True, "leeway": 300},
        )

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

    result = await session.execute(
        text("SELECT id, entity_id, bank_name, account_name FROM bank_accounts WHERE plaid_item_id = :item_id"),
        {"item_id": item_id},
    )
    account = result.fetchone()
    if not account:
        logger.warning("Webhook for unknown item_id", item_id=item_id)
        return

    account_id = account.id
    entity_id = account.entity_id

    if webhook_code in ("INITIAL_UPDATE", "HISTORICAL_UPDATE", "DEFAULT_UPDATE", "SYNC_UPDATES_AVAILABLE"):
        asyncio.create_task(sync_account(str(account_id)))

    elif webhook_code == "ITEM_LOGIN_REQUIRED":
        logger.error("ITEM_LOGIN_REQUIRED", item_id=item_id)
        await session.execute(
            text("""
                UPDATE bank_accounts
                SET plaid_last_error = 'ITEM_LOGIN_REQUIRED', is_active = FALSE
                WHERE id = :id
            """),
            {"id": account_id},
        )
        await session.commit()
        await dispatch.send(
            entity_id=entity_id,
            notification_type='plaid_auth_alert',
            channel='both',
            context={
                "account": f"{account.bank_name} – {account.account_name}",
                "reauth_url": dispatch.get_dashboard_url(f"/reconnect?item_id={item_id}"),
            },
            session=session,
        )

    elif webhook_code == "USER_PERMISSION_REVOKED":
        logger.error("USER_PERMISSION_REVOKED", item_id=item_id)
        await session.execute(
            text("UPDATE bank_accounts SET is_active = FALSE WHERE id = :id"),
            {"id": account_id},
        )
        await session.commit()
        await dispatch.send(
            entity_id=entity_id,
            notification_type='plaid_auth_alert',
            channel='both',
            context={
                "account": f"{account.bank_name} – {account.account_name}",
                "reauth_url": dispatch.get_dashboard_url(f"/reconnect?item_id={item_id}"),
            },
            session=session,
        )

    elif webhook_code == "PENDING_EXPIRATION":
        logger.warning("PENDING_EXPIRATION", item_id=item_id)
        await dispatch.send(
            entity_id=entity_id,
            notification_type='plaid_auth_alert',
            channel='email',
            context={
                "account": f"{account.bank_name} – {account.account_name}",
                "reauth_url": dispatch.get_dashboard_url(f"/reconnect?item_id={item_id}"),
            },
            session=session,
        )
