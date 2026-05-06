import pdfplumber
import pandas as pd
import io
import json
import structlog
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from ..db import AsyncSessionLocal
from ..normalizer import clean_vendor, infer_type
from ..classifier import classify_transaction
from ..allocator import allocate
from ..notifier import dispatch
from ..config import settings
import anthropic
import asyncio

logger = structlog.get_logger()

# Setup Anthropic client
client = None
if settings.ANTHROPIC_API_KEY:
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY.get_secret_value())

async def process_statement(document_id: str):
    """
    Background task to process an uploaded bank statement.
    1. Reads file from storage (Supabase or local).
    2. Extracts text/data.
    3. Uses AI to parse transactions.
    4. Ingests into transactions table.
    """
    async with AsyncSessionLocal() as session:
        # 1. Fetch document metadata
        res = await session.execute(
            text("SELECT id, entity_id, bank_account_id, filename, storage_path, source_type FROM source_documents WHERE id = :id"),
            {"id": document_id}
        )
        doc = res.fetchone()
        if not doc:
            logger.error("Document not found", document_id=document_id)
            return

        # 2. Update status to processing
        await session.execute(
            text("UPDATE source_documents SET parse_status = 'processing' WHERE id = :id"),
            {"id": document_id}
        )
        await session.commit()

        try:
            # For now, we assume local storage for simplicity or Supabase read
            # Since I don't have the Supabase storage logic here, I'll assume it's passed as path
            file_path = doc.storage_path
            if not file_path:
                raise ValueError("No storage path for document")

            # 2. Identify Bank Account if missing
            bank_account_id = doc.bank_account_id
            if not bank_account_id:
                logger.info("Bank account missing, attempting identification from content", document_id=document_id)
                text_for_id = ""
                if doc.filename.lower().endswith('.pdf'):
                    with pdfplumber.open(file_path) as pdf:
                        # Just first page for identification
                        text_for_id = pdf.pages[0].extract_text() or ""
                
                if text_for_id:
                    # Fetch candidate accounts
                    acc_res = await session.execute(
                        text("SELECT id, bank_name, account_name, account_last4 FROM bank_accounts WHERE entity_id = :eid AND is_active = TRUE"),
                        {"eid": doc.entity_id}
                    )
                    candidates = [dict(r._mapping) for r in acc_res.fetchall()]
                    
                    if candidates:
                        id_prompt = f"""
                        Identify which bank account this statement belongs to.
                        Statement text (snippet): {text_for_id[:2000]}
                        
                        Candidates:
                        {json.dumps(candidates, default=str)}
                        
                        Return ONLY the UUID of the matching account, or "null" if no match.
                        """
                        id_resp = await client.messages.create(
                            model="claude-sonnet-4-6",
                            max_tokens=128,
                            messages=[{"role": "user", "content": id_prompt}]
                        )
                        match_id = id_resp.content[0].text.strip().replace('"', '').replace("'", "")
                        if match_id and match_id != "null":
                            bank_account_id = match_id
                            await session.execute(
                                text("UPDATE source_documents SET bank_account_id = :bid WHERE id = :id"),
                                {"bid": bank_account_id, "id": document_id}
                            )
                            await session.commit()
                            logger.info("Identified bank account", account_id=bank_account_id)
                        else:
                            # Auto-create the bank account based on the text
                            create_prompt = f"""
                            Extract the bank account details from this statement to create a new account.
                            Statement text: {text_for_id[:2000]}
                            
                            Return ONLY a JSON object with:
                            - bank_name (string)
                            - account_name (string)
                            - account_last4 (string, up to 4 digits, or null if not found)
                            - account_type (string, e.g. 'checking', 'loan', 'savings')
                            """
                            create_resp = await client.messages.create(
                                model="claude-sonnet-4-6",
                                max_tokens=256,
                                messages=[{"role": "user", "content": create_prompt}]
                            )
                            content = create_resp.content[0].text
                            if "```json" in content:
                                content = content.split("```json")[1].split("```")[0].strip()
                            elif "```" in content:
                                content = content.split("```")[1].split("```")[0].strip()
                            
                            try:
                                acc_details = json.loads(content)
                                query = text("""
                                    INSERT INTO bank_accounts (
                                        entity_id, bank_name, account_name, account_last4, account_type, source_type, is_active
                                    ) VALUES (
                                        :entity_id, :bank_name, :account_name, :last4, :type, 'manual_entry', TRUE
                                    ) RETURNING id
                                """)
                                result = await session.execute(query, {
                                    "entity_id": doc.entity_id,
                                    "bank_name": acc_details.get("bank_name", "Unknown Bank"),
                                    "account_name": acc_details.get("account_name", "Unknown Account"),
                                    "last4": str(acc_details.get("account_last4", ""))[:4] if acc_details.get("account_last4") else None,
                                    "type": acc_details.get("account_type", "checking")
                                })
                                bank_account_id = result.scalar()
                                await session.execute(
                                    text("UPDATE source_documents SET bank_account_id = :bid WHERE id = :id"),
                                    {"bid": bank_account_id, "id": document_id}
                                )
                                await session.commit()
                                logger.info("Auto-created bank account", account_id=bank_account_id)
                            except Exception as e:
                                logger.error("Failed to auto-create bank account", error=str(e))

            if not bank_account_id:
                raise ValueError("Could not identify or create a bank account for this statement.")

            transactions = []
            if doc.filename.lower().endswith('.pdf'):
                transactions = await extract_from_pdf(file_path)
            elif doc.filename.lower().endswith('.csv'):
                transactions = await extract_from_csv(file_path)
            else:
                raise ValueError(f"Unsupported file type: {doc.filename}")

            # 3. Ingest transactions
            processed_count = 0
            for tx_data in transactions:
                try:
                    async with session.begin_nested():
                        inserted = await ingest_extracted_transaction(session, doc, tx_data, bank_account_id)
                        if inserted:
                            processed_count += 1
                except Exception as e:
                    logger.error("Failed to ingest transaction", error=str(e), tx_data=tx_data)
            
            # 4. Final update
            await session.execute(
                text("""
                    UPDATE source_documents 
                    SET parse_status = 'success', 
                        parsed_at = NOW(), 
                        transaction_count = :count 
                    WHERE id = :id
                """),
                {"id": document_id, "count": processed_count}
            )
            await session.commit()
            logger.info("Statement processed successfully", document_id=document_id, count=processed_count)

        except Exception as e:
            await session.rollback()
            logger.error("Failed to process statement", document_id=document_id, error=str(e))
            await session.execute(
                text("UPDATE source_documents SET parse_status = 'failed', parse_error = :err WHERE id = :id"),
                {"id": document_id, "err": str(e)}
            )
            await session.commit()

async def extract_from_pdf(file_path: str) -> List[Dict[str, Any]]:
    """Extracts transactions from a PDF using text extraction + AI."""
    text_content = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text_content += page.extract_text() or ""
    
    if not text_content:
        return []

    # Use AI to parse the text into structured JSON
    if not client:
        raise ValueError("AI client not initialized")

    prompt = f"""
    Extract all transactions from the following bank statement text.
    First, determine the Statement Period (Month and Year) from the text.
    Then, extract each transaction. If the transaction date only contains a day or month/day without a year, use the Statement Period to form a complete YYYY-MM-DD date.
    
    Return a JSON list of objects with these keys: 
    - date (YYYY-MM-DD)
    - description (string)
    - amount (number, positive for deposit/income/credit, negative for withdrawal/expense/debit/charge)
    
    If the statement uses separate columns for Credit/Debit, convert them to signed amounts.
    
    Text:
    {text_content[:15000]}  # Limit to 15k chars for prompt safety
    """

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )
    
    content = response.content[0].text
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    
    return json.loads(content)

async def extract_from_csv(file_path: str) -> List[Dict[str, Any]]:
    """Extracts transactions from a CSV."""
    df = pd.read_csv(file_path)
    # Simple heuristic or AI-assisted mapping could be here.
    # For now, let's use a basic column name check or LLM to map columns.
    # To keep it robust, I'll use LLM to map headers if they are non-standard.
    
    headers = list(df.columns)
    sample_data = df.head(5).to_dict(orient='records')
    
    prompt = f"""
    Given these CSV headers and sample data, identify which columns correspond to 'date', 'description', and 'amount'.
    Headers: {headers}
    Sample: {json.dumps(sample_data)}
    
    Return a JSON object: {{"date_col": "name", "desc_col": "name", "amount_col": "name", "is_amount_signed": bool}}
    """
    
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}]
    )
    
    mapping = json.loads(response.content[0].text.replace("```json", "").replace("```", "").strip())
    
    transactions = []
    for _, row in df.iterrows():
        try:
            date_val = str(row[mapping['date_col']])
            # Simple date parsing or AI could be more robust
            # For now, let's assume standard formats
            amt = float(row[mapping['amount_col']])
            transactions.append({
                "date": date_val,
                "description": str(row[mapping['desc_col']]),
                "amount": amt
            })
        except:
            continue
            
    return transactions

async def ingest_extracted_transaction(session: AsyncSession, doc: Any, tx_data: Dict[str, Any], bank_account_id: Any):
    """Ingests a single transaction from extraction into the DB."""
    amount = Decimal(str(tx_data['amount']))
    vendor_clean = clean_vendor(tx_data['description'])
    tx_type = infer_type(amount)
    
    from datetime import date
    try:
        transaction_date = date.fromisoformat(tx_data['date'])
    except:
        transaction_date = date.today()

    # Duplicate check — scoped strictly to the same bank account to avoid
    # cross-account false positives when different accounts share dates/amounts.
    if bank_account_id:
        dup_check = await session.execute(
            text("""
                SELECT id FROM transactions
                WHERE bank_account_id = :bank_account_id
                  AND entity_id = :entity_id
                  AND transaction_date = :transaction_date
                  AND amount = :amount
                  AND vendor_name_clean = :vendor
            """),
            {
                "bank_account_id": bank_account_id,
                "entity_id": doc.entity_id,
                "transaction_date": transaction_date,
                "amount": amount,
                "vendor": vendor_clean
            }
        )
        if dup_check.fetchone():
            logger.info("Skipping duplicate transaction", amount=float(amount), date=str(transaction_date))
            return False

    tx_model = {
        "entity_id": doc.entity_id,
        "bank_account_id": bank_account_id,
        "transaction_date": transaction_date,
        "amount": amount,
        "vendor_name_clean": vendor_clean,
        "description_clean": tx_data['description'],
        "type": tx_type
    }
    
    try:
        classification = await classify_transaction(session, tx_model)
    except Exception as e:
        logger.error("Classification failed", error=str(e))
        classification = {
            "status": "flagged",
            "method": "fallback",
            "reason": f"Classification error: {str(e)}",
            "account_id": None
        }
    
    query = text("""
        INSERT INTO transactions (
            entity_id, bank_account_id, source_document_id, transaction_date, 
            amount, vendor_name_raw, vendor_name_clean, description, description_clean, status, 
            categorization_method, categorization_reason, ai_raw_response, account_id
        ) VALUES (
            :entity_id, :bank_account_id, :doc_id, :transaction_date,
            :amount, :vendor_name_raw, :vendor_name_clean, :description, :description_clean, :status,
            :categorization_method, :categorization_reason, :ai_raw_response, :account_id
        ) RETURNING id
    """)
    
    params = {
        "entity_id": doc.entity_id,
        "bank_account_id": bank_account_id,
        "doc_id": doc.id,
        "transaction_date": transaction_date,
        "amount": amount,
        "vendor_name_raw": tx_data['description'],
        "vendor_name_clean": vendor_clean,
        "description": tx_data['description'],
        "description_clean": tx_data['description'],
        "status": classification['status'],
        "categorization_method": classification['method'],
        "categorization_reason": classification.get('reason'),
        "ai_raw_response": json.dumps(classification.get('ai_raw')) if classification.get('ai_raw') else None,
        "account_id": classification.get('account_id')
    }
    
    result = await session.execute(query, params)
    tx_id = result.scalar_one()
    
    # Allocations
    try:
        if classification['status'] in ('auto_categorized', 'ai_suggested'):
            # Check if AI suggested a property directly
            direct_property_id = classification.get('property_id')
            if direct_property_id:
                await session.execute(
                    text("""
                        INSERT INTO transaction_allocations (
                            transaction_id, property_id, amount, method, confidence_property
                        ) VALUES (
                            :tid, :pid, :amt, 'direct', :conf
                        )
                    """),
                    {
                        "tid": tx_id,
                        "pid": direct_property_id,
                        "amt": tx_model['amount'],
                        "conf": classification.get('confidence', 0.95)
                    }
                )
            else:
                allocations = await allocate(session, tx_model, classification)
                for alloc in allocations:
                    await session.execute(
                        text("""
                            INSERT INTO transaction_allocations (
                                transaction_id, property_id, amount, percentage, method, confidence_property
                            ) VALUES (
                                :tid, :pid, :amt, :pct, :meth, :conf
                            )
                        """),
                        {
                            "tid": tx_id,
                            "pid": alloc['property_id'],
                            "amt": alloc['amount'],
                            "pct": alloc.get('percentage'),
                            "meth": alloc['method'],
                            "conf": alloc['confidence']
                        }
                    )
    except Exception as e:
        logger.error("Allocation failed", error=str(e), tx_id=tx_id)

    # Notifications
    if amount < -1000:
        # Fire-and-forget notification so we don't block the ingestion loop
        # We don't pass 'session' here so the dispatcher creates its own fresh session
        asyncio.create_task(
            dispatch.send(
                entity_id=doc.entity_id,
                notification_type='large_expense',
                channel='both',
                context={
                    "amount": f"{abs(amount):,.2f}",
                    "vendor": vendor_clean,
                    "date": str(tx_data['date']),
                    "dashboard_url": f"/review?tx_id={tx_id}"
                },
                related_transaction_id=tx_id
            )
        )

    return True
