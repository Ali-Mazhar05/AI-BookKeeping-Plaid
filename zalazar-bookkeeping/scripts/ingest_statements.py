import asyncio
import sys
import os
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from zalazar.db import AsyncSessionLocal
from sqlalchemy import text
from zalazar.statements.processor import process_statement

async def ingest_statements():
    async with AsyncSessionLocal() as session:
        # Get Zalazar entity and its bank account
        res = await session.execute(text("SELECT b.id, b.entity_id FROM bank_accounts b JOIN entities e ON b.entity_id = e.id WHERE e.name = 'Zalazar Holdings' LIMIT 1"))
        acc = res.fetchone()
        if not acc:
            print("Bank account for Zalazar Holdings not found.")
            return
        
        bank_account_id = acc.id
        entity_id = acc.entity_id
        
        files = [
            "Lima One Dec 2025  Statement of Account for Loan #119434 (1).pdf",
            "Lima One Nov 2025  Statement of Account for Loan #119434.pdf",
            "Lima One ZH Oct 2025 Statement for loan 9434.pdf"
        ]
        
        doc_ids = []
        for f in files:
            full_path = os.path.abspath(f"uploads/statements/{f}")
            res = await session.execute(
                text("""
                    INSERT INTO source_documents (entity_id, bank_account_id, source_type, filename, storage_path, parse_status)
                    VALUES (:eid, :bid, 'manual_pdf', :fname, :path, 'pending')
                    RETURNING id
                """),
                {"eid": entity_id, "bid": bank_account_id, "fname": f, "path": full_path}
            )
            doc_id = res.scalar()
            doc_ids.append(doc_id)
            print(f"Registered {f} as doc_id {doc_id}")
            
        await session.commit()
        
        # Now process each one
        print("\nStarting background processing...")
        for did in doc_ids:
            print(f"Processing doc_id {did}...")
            await process_statement(str(did))
            print(f"Finished doc_id {did}")

if __name__ == "__main__":
    asyncio.run(ingest_statements())
