import asyncio
import sys
import os
from uuid import UUID

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from zalazar.db import AsyncSessionLocal
from zalazar.notifier import dispatch

# Target Entity (Zalazar Holdings)
ENTITY_ID = UUID('665c4049-085d-4f32-b2c7-22bd89668e20')

async def run_tests():
    print("=== MANUAL NOTIFICATION TEST SUITE ===")
    
    # Mock IDs for deep linking
    MOCK_TX_ID = UUID('e0000000-0000-0000-0000-000000000001')
    MOCK_RECON_ID = 101

    test_cases = [
        {
            "type": "large_expense",
            "channel": "both",
            "context": {
                "amount": "1,250.00",
                "vendor": "TEST: Home Depot",
                "date": "2026-04-26",
                "dashboard_url": dispatch.get_dashboard_url(f"/review?tx_id={MOCK_TX_ID}")
            }
        },
        {
            "type": "income_received",
            "channel": "both",
            "context": {
                "amount": "3,500.00",
                "source": "TEST: Tenant Rent",
                "date": "2026-04-26",
                "dashboard_url": dispatch.get_dashboard_url(f"/review?tx_id={MOCK_TX_ID}")
            }
        },
        {
            "type": "reconciliation_mismatch",
            "channel": "both",
            "context": {
                "diff": "124.50",
                "account": "TEST: Chase Checking",
                "date": "2026-04-26",
                "plaid_balance": "5,000.00",
                "calculated_balance": "4,875.50",
                "dashboard_url": dispatch.get_dashboard_url(f"/reconciliation?id={MOCK_RECON_ID}")
            }
        },
        {
            "type": "uncategorized",
            "channel": "email",
            "context": {
                "count": 5,
                "dashboard_url": dispatch.get_dashboard_url("/review?status=pending_review")
            }
        },
        {
            "type": "cash_flow_change",
            "channel": "email",
            "context": {
                "delta": "-15% vs last month",
                "period": "April 2026",
                "dashboard_url": dispatch.get_dashboard_url("/analytics/cash-flow")
            }
        },
        {
            "type": "weekly_summary",
            "channel": "email",
            "context": {
                "expenses": "4,230.12",
                "income": "8,100.00",
                "net_flow": "3,869.88",
                "count": 12,
                "pending_count": 5,
                "start_date": "2026-04-20",
                "end_date": "2026-04-26",
                "dashboard_url": dispatch.get_dashboard_url("/")
            }
        }
    ]

    async with AsyncSessionLocal() as session:
        for case in test_cases:
            print(f"\nSending '{case['type']}' via {case['channel']}...")
            try:
                from sqlalchemy import text
                await session.execute(
                    text("DELETE FROM notification_log WHERE entity_id = :eid AND notification_type = :type"),
                    {"eid": ENTITY_ID, "type": case['type']}
                )
                await session.commit()

                await dispatch.send(
                    entity_id=ENTITY_ID,
                    notification_type=case['type'],
                    channel=case['channel'],
                    context=case['context'],
                    session=session
                )
                await session.commit()
                print(f"SUCCESS: {case['type']} triggered.")
            except Exception as e:
                print(f"FAILED: {case['type']} - {e}")
                await session.rollback()

    print("\n=== Test Suite Finished ===")

if __name__ == "__main__":
    asyncio.run(run_tests())
