from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import uuid
import os
import shutil
from zalazar.db import get_db
from zalazar.statements.processor import process_statement

router = APIRouter(prefix="/bank-accounts", tags=["bank-accounts"])

class ManualAccountRequest(BaseModel):
    entity_id: str
    bank_name: str
    account_name: str
    account_last4: Optional[str] = None
    account_type: str = "checking"

@router.post("/manual")
async def create_manual_account(req: ManualAccountRequest, session: AsyncSession = Depends(get_db)):
    """Creates a new manual bank account."""
    try:
        query = text("""
            INSERT INTO bank_accounts (
                entity_id, bank_name, account_name, account_last4, account_type, source_type, is_active
            ) VALUES (
                :entity_id, :bank_name, :account_name, :last4, :type, 'manual_entry', TRUE
            ) RETURNING id
        """)
        result = await session.execute(query, {
            "entity_id": req.entity_id,
            "bank_name": req.bank_name,
            "account_name": req.account_name,
            "last4": req.account_last4,
            "type": req.account_type
        })
        doc_id = result.scalar()
        await session.commit()
        return {"status": "success", "id": doc_id}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{account_id}/upload-statement")
async def upload_statement(
    account_id: uuid.UUID, 
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...), 
    session: AsyncSession = Depends(get_db)
):
    """Uploads a bank statement and triggers processing."""
    try:
        # 1. Fetch account info
        res = await session.execute(
            text("SELECT entity_id FROM bank_accounts WHERE id = :id"),
            {"id": account_id}
        )
        acc = res.fetchone()
        if not acc:
            raise HTTPException(status_code=404, detail="Account not found")

        # 2. Save file locally for now (In production use Supabase Storage/S3)
        upload_dir = "uploads/statements"
        os.makedirs(upload_dir, exist_ok=True)
        file_id = str(uuid.uuid4())
        file_ext = os.path.splitext(file.filename)[1]
        storage_path = os.path.join(upload_dir, f"{file_id}{file_ext}")
        
        with open(storage_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 3. Create source_documents record
        source_type = 'manual_pdf' if file_ext.lower() == '.pdf' else 'manual_csv'
        
        query = text("""
            INSERT INTO source_documents (
                entity_id, bank_account_id, source_type, filename, storage_path, parse_status
            ) VALUES (
                :entity_id, :account_id, :source_type, :filename, :path, 'pending'
            ) RETURNING id
        """)
        result = await session.execute(query, {
            "entity_id": acc.entity_id,
            "account_id": account_id,
            "source_type": source_type,
            "filename": file.filename,
            "path": os.path.abspath(storage_path)
        })
        doc_id = result.scalar()
        await session.commit()

        # 4. Trigger processing
        background_tasks.add_task(process_statement, str(doc_id))

        return {"status": "uploaded", "document_id": doc_id}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("")
async def list_bank_accounts(entity_id: str, session: AsyncSession = Depends(get_db)):
    """Lists all bank accounts for an entity including source_type."""
    query = text("""
        SELECT id, bank_name, account_name, account_last4, account_type, source_type, 
               CASE 
                   WHEN source_type = 'manual_entry' THEN COALESCE((SELECT SUM(amount) FROM transactions WHERE bank_account_id = bank_accounts.id), 0)
                   ELSE current_balance 
               END as current_balance, 
               last_synced_at, is_active
        FROM bank_accounts
        WHERE entity_id = :entity_id AND is_active = TRUE
    """)
    result = await session.execute(query, {"entity_id": entity_id})
    return {"data": [dict(row._mapping) for row in result.fetchall()]}
@router.delete("/{account_id}")
async def delete_bank_account(account_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    """Deletes (deactivates) a bank account."""
    try:
        await session.execute(
            text("UPDATE bank_accounts SET is_active = FALSE WHERE id = :id"),
            {"id": account_id}
        )
        await session.commit()
        return {"status": "deleted"}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload-global")
async def upload_statement_global(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...), 
    session: AsyncSession = Depends(get_db)
):
    """Uploads a bank statement WITHOUT a pre-selected account. Account will be identified from content."""
    try:
        # 1. Fetch any entity (using first one for now)
        res = await session.execute(text("SELECT id FROM entities LIMIT 1"))
        entity = res.fetchone()
        if not entity:
            raise HTTPException(status_code=400, detail="No entity found to link statement to.")
        
        # 2. Save file
        upload_dir = "uploads/statements"
        os.makedirs(upload_dir, exist_ok=True)
        file_id = str(uuid.uuid4())
        file_ext = os.path.splitext(file.filename)[1]
        storage_path = os.path.join(upload_dir, f"{file_id}{file_ext}")
        
        with open(storage_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 3. Create source_documents record (bank_account_id is null)
        source_type = 'manual_pdf' if file_ext.lower() == '.pdf' else 'manual_csv'
        query = text("""
            INSERT INTO source_documents (
                entity_id, bank_account_id, source_type, filename, storage_path, parse_status
            ) VALUES (
                :entity_id, NULL, :source_type, :filename, :path, 'pending'
            ) RETURNING id
        """)
        result = await session.execute(query, {
            "entity_id": entity.id,
            "source_type": source_type,
            "filename": file.filename,
            "path": storage_path
        })
        doc_id = result.scalar()
        await session.commit()

        # 4. Trigger processing
        background_tasks.add_task(process_statement, str(doc_id))

        return {"status": "uploaded", "document_id": doc_id}
    except Exception as e:
        await session.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
