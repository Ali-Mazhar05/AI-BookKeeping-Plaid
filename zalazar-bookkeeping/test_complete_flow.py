import asyncio
import structlog
from uuid import UUID
from sqlalchemy import text
from src.zalazar.db import AsyncSessionLocal
from src.zalazar.notifier import dispatch
from src.zalazar.config import settings

# Configure logging
structlog.configure()
logger = structlog.get_logger()

# Test Entity ID from your database (Zalazar Holdings)
ENTITY_ID = UUID('a0000000-0000-0000-0000-000000000001')

async def test_complete_notification_flow():
    print("--- Starting Complete Notification Flow Test ---")
    print(f"Target Entity: {ENTITY_ID}")
    print(f"SMS Recipient (Config): {settings.SMS_RECIPIENT}")
    print(f"Email Recipient (Config): {settings.EMAIL_RECIPIENT}")
    print("-" * 45)

    async with AsyncSessionLocal() as session:
        # 1. Ensure Notification Settings exist for this entity
        print("[1/3] Ensuring notification settings are configured in DB...")
        await session.execute(
            text("""
                INSERT INTO notification_settings (
                    entity_id, sms_recipient, email_recipient, 
                    notify_large_expense, notify_income_received, notify_reconciliation_fail
                ) VALUES (
                    :eid, :sms, :email, TRUE, TRUE, TRUE
                ) ON CONFLICT (entity_id) DO UPDATE SET
                    sms_recipient = EXCLUDED.sms_recipient,
                    email_recipient = EXCLUDED.email_recipient,
                    notify_large_expense = TRUE;
            """),
            {
                "eid": ENTITY_ID,
                "sms": settings.SMS_RECIPIENT,
                "email": settings.EMAIL_RECIPIENT
            }
        )
        await session.commit()
        print("Settings synchronized.")

        # 2. Trigger the notification flow
        print("\n[2/3] Triggering 'large_expense' notification (Both Email & SMS)...")
        try:
            # This calls the main dispatcher which:
            # - Renders the template
            # - Logs to database
            # - Sends SMS via RingCentral
            # - Sends Email via Gmail/SMTP
            await dispatch.send(
                entity_id=ENTITY_ID,
                notification_type='large_expense',
                channel='both',
                context={
                    "amount": "1,250.00",
                    "vendor": "TEST VENDOR (RingCentral Flow)",
                    "date": "2026-04-26",
                    "dashboard_url": "https://zalazar.example/dashboard/review"
                },
                session=session
            )
            await session.commit()
            print("Notification flow completed successfully!")
        except Exception as e:
            print(f"FLOW FAILED! Error: {str(e)}")
            await session.rollback()
            return

        # 3. Verify the Log Entry
        print("\n[3/3] Verifying database log entry...")
        result = await session.execute(
            text("""
                SELECT id, status, provider, provider_message_id, error, created_at 
                FROM notification_log 
                WHERE entity_id = :eid 
                ORDER BY created_at DESC LIMIT 1
            """),
            {"eid": ENTITY_ID}
        )
        log = result.fetchone()
        if log:
            print(f"Recent Log ID: {log.id}")
            print(f"Status:       {log.status}")
            print(f"Provider:     {log.provider}")
            print(f"Message ID:   {log.provider_message_id}")
            if log.error:
                print(f"Error:        {log.error}")
        else:
            print("No log entry found!")

    print("-" * 45)
    print("Test finished.")

if __name__ == "__main__":
    asyncio.run(test_complete_notification_flow())
