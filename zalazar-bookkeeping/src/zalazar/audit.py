from uuid import UUID
from typing import Any, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import json
import structlog

logger = structlog.get_logger()

async def log_action(
    session: AsyncSession,
    entity_type: str,
    entity_id: UUID,
    action: str,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    changed_by: Optional[str] = None,
    reason: Optional[str] = None
):
    """Writes an entry to the audit_log table."""
    try:
        query = text("""
            INSERT INTO audit_log (
                entity_type, entity_id, action, before_state, after_state, changed_by, reason
            ) VALUES (
                :type, :id, :action, :before, :after, :by, :reason
            )
        """)
        # Convert UUIDs and decimals to strings for JSON serialization if needed
        # but json.dumps handles some things. For robust implementation, use a custom encoder.
        
        def default_serializer(obj):
            if isinstance(obj, UUID):
                return str(obj)
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            return str(obj)

        await session.execute(query, {
            "type": entity_type,
            "id": entity_id,
            "action": action,
            "before": json.dumps(before, default=default_serializer) if before else None,
            "after": json.dumps(after, default=default_serializer) if after else None,
            "by": changed_by or 'system',
            "reason": reason
        })
    except Exception as e:
        logger.error("Failed to write audit log", error=str(e), entity_id=str(entity_id))
        # Don't raise, we don't want audit logging to break the main transaction
        # unless it's a strict requirement.
