from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict
import structlog

from zalazar.db import get_db
from zalazar.jarvis.agent import ask_jarvis

logger = structlog.get_logger()
router = APIRouter(prefix="/jarvis", tags=["jarvis"])

class AskJarvisRequest(BaseModel):
    entity_id: str
    question: str
    conversation_history: Optional[List[Dict[str, str]]] = None

@router.post("/ask")
async def ask(req: AskJarvisRequest, session: AsyncSession = Depends(get_db)):
    """Ask JARVIS a question via API."""
    try:
        answer = await ask_jarvis(session, req.entity_id, req.question, req.conversation_history)
        return {"answer": answer}
    except Exception as e:
        logger.error("Ask JARVIS failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhook")
async def ringcentral_webhook(request: Request, response: Response, session: AsyncSession = Depends(get_db)):
    """
    Inbound RingCentral Webhook for JARVIS.
    Handles RingCentral's Validation-Token handshake and processes inbound SMS.
    """
    # 1. Handle RingCentral Validation-Token handshake
    validation_token = request.headers.get("Validation-Token")
    if validation_token:
        response.headers["Validation-Token"] = validation_token
        return {"status": "validated"}

    # 2. Process Notification
    try:
        payload = await request.json()
        logger.info("RingCentral webhook received", event=payload.get("event"))

        # Check if it's an inbound SMS
        body = payload.get("body", {})
        if payload.get("event", "").endswith("/message-store/instant?type=SMS"):
            direction = body.get("direction")
            if direction == "Inbound":
                from_num = body.get("from", {}).get("phoneNumber")
                text = body.get("subject") # SMS text is in subject for instant messages
                
                logger.info("Inbound JARVIS query", from_number=from_num, text=text)
                
                # TODO: Identify entity_id from from_num
                # For now, use the default entity or a placeholder
                # answer = await ask_jarvis(session, "default-entity-id", text)
                # logger.info("JARVIS response", answer=answer)
                
                return {"status": "received", "action": "jarvis_query_routed"}

        return {"status": "received", "action": "ignored"}
    except Exception as e:
        logger.error("RingCentral webhook processing failed", error=str(e))
        return {"status": "error", "detail": str(e)}
