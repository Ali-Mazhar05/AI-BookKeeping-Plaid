import asyncio
import sys
import os
from datetime import datetime, timedelta
from decimal import Decimal

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from zalazar.db import AsyncSessionLocal
from zalazar.notifier import dispatch
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as session:
        # 1. Get entities to process
        res = await session.execute(text("SELECT id, name FROM entities"))
        entities = res.fetchall()
        
        for entity in entities:
            print(f"Processing weekly summary for {entity.name}...")
            
            # 2. Get stats for last 7 days
            seven_days_ago = datetime.now() - timedelta(days=7)
            
            # Expenses
            exp_res = await session.execute(
                text("SELECT SUM(amount) FROM transactions WHERE entity_id = :eid AND amount < 0 AND transaction_date >= :dt AND status != 'excluded'"),
                {"eid": entity.id, "dt": seven_days_ago.date()}
            )
            expenses = exp_res.scalar() or Decimal('0')
            
            # Income
            inc_res = await session.execute(
                text("SELECT SUM(amount) FROM transactions WHERE entity_id = :eid AND amount > 0 AND transaction_date >= :dt AND status != 'excluded'"),
                {"eid": entity.id, "dt": seven_days_ago.date()}
            )
            income = inc_res.scalar() or Decimal('0')
            
            # Count reviewed
            count_res = await session.execute(
                text("SELECT COUNT(*) FROM transactions WHERE entity_id = :eid AND status IN ('reviewed', 'auto_categorized') AND transaction_date >= :dt"),
                {"eid": entity.id, "dt": seven_days_ago.date()}
            )
            count = count_res.scalar() or 0
            
            # Count currently pending
            pend_res = await session.execute(
                text("SELECT COUNT(*) FROM transactions WHERE entity_id = :eid AND status IN ('pending_review', 'ai_suggested', 'flagged')"),
                {"eid": entity.id}
            )
            pending_count = pend_res.scalar() or 0
            
            # 3. Send notification
            try:
                await dispatch.send(
                    entity_id=entity.id,
                    notification_type='weekly_summary',
                    channel='email',
                    context={
                        "expenses": f"{abs(expenses):,.2f}",
                        "income": f"{income:,.2f}",
                        "net_flow": f"{(income + expenses):,.2f}",
                        "count": count,
                        "pending_count": pending_count,
                        "dashboard_url": dispatch.get_dashboard_url("/")
                    }
                )
                print(f"Weekly summary sent for {entity.name} to alimazhar3005@gmail.com")
            except Exception as e:
                print(f"Failed to send weekly summary for {entity.name}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
