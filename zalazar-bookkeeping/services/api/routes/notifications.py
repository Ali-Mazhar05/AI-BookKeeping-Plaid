from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import structlog
from datetime import datetime

from zalazar.db import get_db

logger = structlog.get_logger()
router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.post("/callback")
async def ringcentral_callback(request: Request, response: Response, session: AsyncSession = Depends(get_db)):
    """
    RingCentral Status Callback.
    Updates notification_log with delivery status (Sent, Delivered, Failed).
    """
    # 1. Validation handshake
    validation_token = request.headers.get("Validation-Token")
    if validation_token:
        response.headers["Validation-Token"] = validation_token
        return {"status": "validated"}

    # 2. Process status update
    try:
        payload = await request.json()
        body = payload.get("body", {})
        
        # Check if it's a message status update
        message_id = body.get("id")
        status = body.get("messageStatus") # e.g., 'Sent', 'Delivered', 'DeliveryFailed'
        
        if message_id and status:
            logger.info("Notification status update", message_id=message_id, status=status)
            
            # Map RingCentral status to our enum
            status_map = {
                'Sent': 'sent',
                'Delivered': 'delivered',
                'DeliveryFailed': 'failed',
                'SendingFailed': 'failed'
            }
            mapped_status = status_map.get(status, 'pending')
            
            # Update log
            query = text("""
                UPDATE notification_log 
                SET status = :status, 
                    delivered_at = :now,
                    error = CASE WHEN :status = 'failed' THEN 'RingCentral delivery failed' ELSE error END
                WHERE provider_message_id = :mid
            """)
            await session.execute(query, {
                "status": mapped_status,
                "now": datetime.utcnow() if mapped_status == 'delivered' else None,
                "mid": str(message_id)
            })
            await session.commit()
            
            return {"status": "updated"}

        return {"status": "ignored"}
    except Exception as e:
        logger.error("Callback processing failed", error=str(e))
        return {"status": "error", "detail": str(e)}
