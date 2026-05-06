import json
from uuid import UUID
from typing import Dict, Any, Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from jinja2 import Environment, FileSystemLoader, select_autoescape
import os
from . import sms
from . import email
from ..db import AsyncSessionLocal
from ..config import settings

# Setup Jinja2 environment
template_dir = os.path.join(os.path.dirname(__file__), "templates")
jinja_env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=select_autoescape()
)

logger = structlog.get_logger()

def get_dashboard_url(path: str = "") -> str:
    """Builds an absolute URL for the dashboard."""
    base = settings.DASHBOARD_URL.rstrip('/')
    if not path:
        return base
    return f"{base}/{path.lstrip('/')}"


async def get_notification_settings(session: AsyncSession, entity_id: UUID) -> Any:
    result = await session.execute(
        text("SELECT * FROM notification_settings WHERE entity_id = :entity_id"),
        {"entity_id": entity_id}
    )
    row = result.fetchone()
    return row._mapping if row else None

def _is_enabled(user_settings: Any, notification_type: str) -> bool:
    if not user_settings:
        return True
    mapping = {
        'large_expense': user_settings.get('notify_large_expense', True),
        'uncategorized': user_settings.get('notify_uncategorized', True),
        'income_received': user_settings.get('notify_income_received', True),
        'cash_flow_change': user_settings.get('notify_cash_flow_change', True),
        'reconciliation_mismatch': user_settings.get('notify_reconciliation_fail', True),
        'weekly_summary': True,
    }
    return mapping.get(notification_type, False)

def _recipient_for(user_settings: Any, channel: str) -> str:
    if channel == 'sms':
        return (user_settings.get('sms_recipient') if user_settings else None) or settings.SMS_RECIPIENT
    elif channel == 'email':
        return (user_settings.get('email_recipient') if user_settings else None) or settings.EMAIL_RECIPIENT
    return ''

def render_template(notification_type: str, context: Dict[str, Any], format: str = 'text') -> str:
    """Renders a Jinja2 template for the given notification type."""
    suffix = ".html.jinja2" if format == 'html' else ".jinja2"
    try:
        template = jinja_env.get_template(f"{notification_type}{suffix}")
        return template.render(**context)
    except Exception as e:
        if format == 'html':
            return None # Don't fallback to basic for HTML
            
        logger.warning("Template not found or render error, falling back to basic formatting", 
                       type=notification_type, error=str(e))
        # Fallback logic
        templates = {
            'large_expense': "Large expense detected: ${amount} at {vendor}.",
            'reconciliation_mismatch': "Reconciliation mismatch of ${diff} on account {account}.",
            'income_received': "Income received: ${amount} from {source}.",
            'uncategorized': "You have uncategorized transactions waiting.",
            'cash_flow_change': "Significant cash flow change: {delta}.",
            'weekly_summary': "Weekly Summary: Total Expense: ${expenses}, Total Income: ${income}."
        }
        tmpl = templates.get(notification_type, "Notification: {notification_type}")
        try:
            return tmpl.format(**context, notification_type=notification_type)
        except KeyError:
            return tmpl
        except Exception:
            return tmpl

def _subject_for(notification_type: str, context: Dict[str, Any]) -> str:
    subjects = {
        'large_expense': "Alert: Large Expense",
        'reconciliation_mismatch': "Alert: Reconciliation Mismatch",
        'income_received': "Alert: Income Received",
        'uncategorized': "Action Required: Review Transactions",
        'cash_flow_change': "Alert: Cash Flow Change",
        'weekly_summary': "Weekly Financial Summary"
    }
    return subjects.get(notification_type, "System Notification")

async def send(
    entity_id: UUID,
    notification_type: str,
    channel: str,
    context: Dict[str, Any],
    related_transaction_id: Optional[UUID] = None,
    related_reconciliation_id: Optional[UUID] = None,
    related_property_id: Optional[UUID] = None,
    session: Optional[AsyncSession] = None,
):
    if session is None:
        async with AsyncSessionLocal() as new_session:
            res = await _send_impl(
                new_session, entity_id, notification_type, channel, context,
                related_transaction_id, related_reconciliation_id, related_property_id
            )
            await new_session.commit()
            return res
    else:
        return await _send_impl(
            session, entity_id, notification_type, channel, context,
            related_transaction_id, related_reconciliation_id, related_property_id
        )

async def _is_throttled(session: AsyncSession, entity_id: UUID, notification_type: str) -> bool:
    """Checks if a notification should be throttled (max 1 per hour for high-freq types)."""
    if notification_type in ('large_expense', 'uncategorized', 'cash_flow_change'):
        query = text("""
            SELECT COUNT(*) 
            FROM notification_log 
            WHERE entity_id = :eid 
              AND notification_type = :type 
              AND created_at > NOW() - INTERVAL '1 hour'
              AND status NOT IN ('failed', 'suppressed')
        """)
        res = await session.execute(query, {"eid": entity_id, "type": notification_type})
        return res.scalar() >= 1
    return False

async def _send_impl(
    session: AsyncSession,
    entity_id: UUID,
    notification_type: str,
    channel: str,
    context: Dict[str, Any],
    related_transaction_id: Optional[UUID] = None,
    related_reconciliation_id: Optional[UUID] = None,
    related_property_id: Optional[UUID] = None,
):
        user_settings = await get_notification_settings(session, entity_id)
        if not _is_enabled(user_settings, notification_type):
            logger.info("Notification suppressed by settings", type=notification_type)
            return

        # Check throttling
        if await _is_throttled(session, entity_id, notification_type):
            logger.info("Notification throttled", type=notification_type, entity_id=str(entity_id))
            status = 'suppressed'
            reason = 'throttled'
        else:
            status = 'pending'
            reason = None

        body = render_template(notification_type, context, format='text')
        html_body = render_template(notification_type, context, format='html') if channel in ('email', 'both') else None
        subject = _subject_for(notification_type, context) if channel in ('email', 'both') else None
        
        log_res = await session.execute(
            text("""
                INSERT INTO notification_log (
                    entity_id, notification_type, channel, recipient, subject, body, payload,
                    related_transaction_id, related_reconciliation_id, related_property_id, 
                    status, error
                ) VALUES (
                    :eid, :type, :channel, :recipient, :subject, :body, CAST(:payload AS JSONB),
                    :rtx_id, :rrecon_id, :rprop_id, :status, :reason
                ) RETURNING id
            """),
            {
                "eid": entity_id, "type": notification_type, "channel": channel,
                "recipient": _recipient_for(user_settings, channel), "subject": subject,
                "body": body, "payload": json.dumps(context), 
                "rtx_id": related_transaction_id, "rrecon_id": related_reconciliation_id,
                "rprop_id": related_property_id,
                "status": status, "reason": reason
            }
        )
        log_id = log_res.scalar_one()
        await session.flush() 

        if status == 'suppressed':
            return log_id

        try:
            if channel in ('sms', 'both'):
                recipient = _recipient_for(user_settings, 'sms')
                if recipient:
                    msg_id = await sms.send(recipient, body)
                    await session.execute(text("UPDATE notification_log SET status = 'sent', provider = 'ringcentral', provider_message_id = :mid WHERE id = :lid"), {"mid": msg_id, "lid": log_id})
                    
            if channel in ('email', 'both'):
                recipient = _recipient_for(user_settings, 'email')
                if recipient:
                    msg_id = await email.send(recipient, subject, body, html_body=html_body)
                    await session.execute(text("UPDATE notification_log SET status = 'sent', provider = 'gmail', provider_message_id = :mid WHERE id = :lid"), {"mid": msg_id, "lid": log_id})
            
            await session.flush()
            
        except Exception as e:
            logger.error("Failed to send notification", error=str(e))
            await session.execute(text("UPDATE notification_log SET status = 'failed', error = :err WHERE id = :lid"), {"err": str(e), "lid": log_id})
            await session.flush()
            raise


if __name__ == "__main__":
    import asyncio
    from ..config import settings
    
    async def test():
        # Test Entity ID
        ENTITY_ID = UUID('a0000000-0000-0000-0000-000000000001')
        print(f"Testing dispatcher for entity {ENTITY_ID}...")
        try:
            await send(
                entity_id=ENTITY_ID,
                notification_type='large_expense',
                channel='both',
                context={
                    "amount": "1,250.00", 
                    "vendor": "CLI TEST",
                    "date": "2026-04-26",
                    "dashboard_url": "https://zalazar.example/dashboard/review"
                }
            )
            print("Test notification sent successfully!")
        except Exception as e:
            print(f"Test failed: {e}")

    asyncio.run(test())
