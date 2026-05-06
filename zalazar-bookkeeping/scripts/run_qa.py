import asyncio
import json
import os
from decimal import Decimal
from datetime import date
from typing import List, Dict, Any
import structlog
from sqlalchemy import text

from zalazar.db import AsyncSessionLocal
from zalazar.normalizer import clean_vendor, infer_type
from zalazar.classifier import classify_transaction
from zalazar.allocator import allocate

logger = structlog.get_logger()

def load_fixture(path: str) -> List[Dict[str, Any]]:
    with open(path, 'r') as f:
        return json.load(f)

async def evaluate_transaction(session, tx: Dict[str, Any]) -> Dict[str, Any]:
    # Mocking necessary context
    amount = Decimal(str(tx['amount']))
    vendor_clean = clean_vendor(tx['vendor_raw'])
    tx_type = infer_type(amount)
    
    # We use dummy UUIDs for entity/account in this pure-logic QA
    tx_model = {
        "entity_id": "00000000-0000-0000-0000-000000000000",
        "bank_account_id": "00000000-0000-0000-0000-000000000000",
        "transaction_date": tx['date'],
        "amount": amount,
        "vendor_name_clean": vendor_clean,
        "description_clean": tx['description_raw'],
        "account_name": tx['account_name'],
        "type": tx_type
    }
    
    classification = await classify_transaction(session, tx_model)
    
    allocated = []
    if classification['status'] == 'auto_categorized':
        allocations = await allocate(session, tx_model, classification)
        allocated = allocations
        
    return {
        "expected_account": tx['expected_account_code'],
        "actual_account": classification.get('account_id'),
        "status": classification['status'],
        "expected_allocations": tx.get('expected_property_allocation', []),
        "actual_allocations": allocated,
        "vendor_clean": vendor_clean
    }

async def run_qa():
    fixture_path = os.path.join(os.path.dirname(__file__), '..', 'tests', 'fixtures', 'qa_transactions.json')
    data = load_fixture(fixture_path)
    
    total = len(data)
    auto_categorized = 0
    correct_account = 0
    
    results = []
    
    async with AsyncSessionLocal() as session:
        for tx in data:
            res = await evaluate_transaction(session, tx)
            results.append(res)
            
            if res['status'] == 'auto_categorized':
                auto_categorized += 1
                
            actual_code = None
            if res['actual_account']:
                acc_res = await session.execute(text("SELECT code FROM accounts WHERE id = :id"), {"id": res['actual_account']})
                actual_code = acc_res.scalar()
                
            if actual_code == res['expected_account']:
                correct_account += 1
                
    auto_rate = (auto_categorized / total) * 100 if total > 0 else 0
    acc_rate = (correct_account / total) * 100 if total > 0 else 0
    
    report = f"# QA Report ({date.today().isoformat()})\n\n"
    report += f"**Total Transactions:** {total}\n"
    report += f"**Auto-Categorized Rate:** {auto_rate:.1f}%\n"
    report += f"**Account Accuracy:** {acc_rate:.1f}%\n\n"
    report += "## Details\n\n"
    
    for r in results:
        report += f"- Vendor: {r['vendor_clean']} | Expected: {r['expected_account']} | Actual: {r['actual_account']} | Status: {r['status']}\n"
        
    report_path = os.path.join(os.path.dirname(__file__), '..', f'qa_report_{date.today().strftime("%Y%m%d")}.md')
    with open(report_path, 'w') as f:
        f.write(report)
        
    logger.info("QA run complete", total=total, auto_rate=auto_rate, acc_rate=acc_rate)
    print(f"Report saved to {report_path}")

if __name__ == "__main__":
    asyncio.run(run_qa())
