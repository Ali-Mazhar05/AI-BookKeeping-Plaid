import asyncio
import structlog
from src.zalazar.notifier import sms
from src.zalazar.config import settings

# Configure logging for the test script
structlog.configure()
logger = structlog.get_logger()

async def test_ringcentral_sms():
    print("--- RingCentral SMS Test Script ---")
    print(f"From Number: {settings.RC_FROM_NUMBER}")
    print(f"Recipient:   {settings.SMS_RECIPIENT}")
    print(f"Server URL:  {settings.RC_SERVER_URL}")
    print("-" * 35)

    test_cases = [
        {
            "name": "Testing: Large Expense Alert",
            "body": "Testing: Alert: A large expense of $750.00 was detected at 'Floor & Decor' on 2026-04-12. Please review in the Zalazar Bookkeeping dashboard."
        },
        {
            "name": "Testing: Income Received",
            "body": "Testing: Good news! Income of $3,200.00 was received from 'Red River' on 2026-04-20."
        },
        {
            "name": "Testing: Reconciliation Mismatch",
            "body": "Testing: Alert: A reconciliation mismatch of $12.25 was found on account 'WF Business Checking'. Immediate action required."
        }
    ]

    for case in test_cases:
        print(f"Sending test message: {case['name']}...")
        try:
            # We use the actual recipient from settings
            msg_id = await sms.send(settings.SMS_RECIPIENT, case['body'])
            print(f"SUCCESS! Message ID: {msg_id}")
        except Exception as e:
            print(f"FAILED! Error: {str(e)}")
        print("-" * 35)

if __name__ == "__main__":
    asyncio.run(test_ringcentral_sms())
