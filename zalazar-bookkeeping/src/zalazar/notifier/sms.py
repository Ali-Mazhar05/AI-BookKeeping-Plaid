import structlog
from ringcentral import SDK
from ..config import settings
import uuid
import asyncio

logger = structlog.get_logger()

async def send(recipient: str, body: str) -> str:
    """Send SMS via RingCentral."""
    if not settings.RC_CLIENT_ID or not settings.RC_JWT:
        logger.warning("RingCentral credentials missing. SMS not sent.", recipient=recipient)
        return f"mock_rc_sms_{uuid.uuid4()}"

    try:
        # RingCentral's SDK is synchronous. In production FastAPI, run in threadpool.
        def _send_impl():
            sdk = SDK(
                settings.RC_CLIENT_ID, 
                settings.RC_CLIENT_SECRET.get_secret_value(), 
                settings.RC_SERVER_URL
            )
            platform = sdk.platform()
            platform.login(jwt=settings.RC_JWT.get_secret_value())
            
            params = {
                'from': {'phoneNumber': settings.RC_FROM_NUMBER},
                'to': [{'phoneNumber': recipient}],
                'text': body
            }
            response = platform.post('/restapi/v1.0/account/~/extension/~/sms', params)
            return str(response.json().id)

        msg_id = await asyncio.to_thread(_send_impl)
        logger.info("RingCentral SMS sent successfully", recipient=recipient, message_id=msg_id)
        return msg_id
    except Exception as e:
        logger.error("RingCentral SMS send failed", error=str(e))
        raise
