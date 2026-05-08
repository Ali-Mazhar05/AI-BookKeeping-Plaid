import asyncio
import threading
import uuid

import structlog
from ringcentral import SDK

from ..config import settings

logger = structlog.get_logger()

# Cached authenticated platform — avoids re-authenticating on every SMS
# (each login hits the /oauth/token endpoint and counts against RC rate limits).
_platform = None
_platform_lock = threading.Lock()


def _get_platform():
    global _platform
    with _platform_lock:
        if _platform is None or not _platform.logged_in():
            sdk = SDK(
                settings.RC_CLIENT_ID,
                settings.RC_CLIENT_SECRET.get_secret_value(),
                settings.RC_SERVER_URL,
            )
            p = sdk.platform()
            p.login(jwt=settings.RC_JWT.get_secret_value())
            _platform = p
        return _platform


async def send(recipient: str, body: str) -> str:
    """Send SMS via RingCentral."""
    if not settings.RC_CLIENT_ID or not settings.RC_JWT:
        logger.warning("RingCentral credentials missing. SMS not sent.", recipient=recipient)
        return f"mock_rc_sms_{uuid.uuid4()}"

    try:
        def _send_impl():
            platform = _get_platform()
            params = {
                "from": {"phoneNumber": settings.RC_FROM_NUMBER},
                "to": [{"phoneNumber": recipient}],
                "text": body,
            }
            response = platform.post("/restapi/v1.0/account/~/extension/~/sms", params)
            return str(response.json().id)

        msg_id = await asyncio.to_thread(_send_impl)
        logger.info("RingCentral SMS sent successfully", recipient=recipient, message_id=msg_id)
        return msg_id
    except Exception as e:
        logger.error("RingCentral SMS send failed", error=str(e))
        raise
