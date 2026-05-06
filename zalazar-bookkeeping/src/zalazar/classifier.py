from typing import Optional, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import structlog
from .config import settings
import anthropic
import json

logger = structlog.get_logger()

# Setup Anthropic client
client = None
if settings.ANTHROPIC_API_KEY:
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY.get_secret_value())

async def match_rule(session: AsyncSession, vendor_clean: str) -> Optional[dict]:
    query = """
        SELECT id, pattern, account_id, default_property_id, confidence,
               property_attribution, match_type
        FROM vendor_rules
        WHERE is_active = TRUE
          AND (
              (match_type = 'exact' AND pattern = :vendor)
              OR (match_type = 'contains' AND :vendor ILIKE '%' || pattern || '%')
              OR (match_type = 'regex' AND :vendor ~* pattern)
          )
        ORDER BY confidence DESC, LENGTH(pattern) DESC
        LIMIT 1
    """
    result = await session.execute(text(query), {"vendor": vendor_clean})
    row = result.fetchone()
    if row:
        return dict(row._mapping)
    return None

async def classify_transaction(session: AsyncSession, tx: Dict[str, Any]) -> Dict[str, Any]:
    """
    State machine:
    1. Check vendor_rules
    2. If rule >= 0.95 -> auto_categorized
    3. Else fallback to AI
    """
    vendor_clean = tx.get("vendor_name_clean", "") or tx.get("description_clean", "") or ""
    
    # Check for internal transfers first (bypasses rules and AI)
    from .normalizer import is_transfer
    if is_transfer(vendor_clean):
        return {
            "status": "excluded",
            "method": "transfer_logic",
            "reason": "Detected internal transfer pattern",
            "account_id": "a0000000-0000-0000-0000-000000003501", # Internal Transfer
            "property_id": None
        }

    rule = await match_rule(session, vendor_clean)
    
    if rule and rule["confidence"] >= 0.95 and rule["account_id"] is not None:
        # Check if property attribution is resolvable
        attr = rule["property_attribution"]
        if attr in ("direct", "even_split"):
            return {
                "status": "auto_categorized",
                "method": "rule",
                "reason": f"Matched rule {rule['id']}",
                "account_id": rule["account_id"],
                "property_id": rule["default_property_id"] if attr == "direct" else None,
                "rule": rule
            }
        else:
            return {
                "status": "flagged",
                "method": "rule",
                "reason": "Rule matched but property attribution requires review",
                "account_id": rule["account_id"],
                "rule": rule
            }
            
    # Fallback to AI
    if not client:
        return {
            "status": "pending_review",
            "method": "none",
            "reason": "No rule match, Gemini API client not initialized"
        }

    try:
        # Fetch accounts and properties for context
        acc_res = await session.execute(text("SELECT id, name, code FROM accounts WHERE is_assignable = TRUE"))
        accounts = [{"id": str(r.id), "name": r.name, "code": r.code} for r in acc_res.fetchall()]

        
        prop_res = await session.execute(text("SELECT id, name FROM properties WHERE is_active = TRUE"))
        properties = [{"id": str(r.id), "name": r.name} for r in prop_res.fetchall()]

        prompt = f"""
        Categorize this real estate transaction for a bookkeeping system.
        
        Transaction: {tx.get('description_clean')}
        Amount: {tx.get('amount')}
        Date: {tx.get('transaction_date')}
        
        Available Accounts:
        {json.dumps(accounts, indent=2)}
        
        Available Properties:
        {json.dumps(properties, indent=2)}
        
        Return exactly a JSON object:
        {{
            "account_id": "UUID",
            "property_id": "UUID or null",
            "confidence": 0.0 to 1.0,
            "reasoning": "Simple 10-15 word explanation for a real estate dealer. NO accounting jargon (like ACH, principal, escrow). Just plain English."
        }}
        """

        # Using Claude
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Claude returns content as a list of text blocks
        response_text = response.content[0].text
        # Clean potential markdown code blocks
        if response_text.startswith("```json"):
            response_text = response_text.replace("```json", "").replace("```", "").strip()
        elif response_text.startswith("```"):
            response_text = response_text.replace("```", "").strip()
            
        ai_data = json.loads(response_text)
        
        # Determine status based on confidence threshold (0.85)
        confidence = ai_data.get("confidence", 0)
        status = "ai_suggested" if confidence >= 0.85 else "pending_review"
            
        # Log usage (M4.4)
        try:
            usage = response.usage
            await log_llm_usage(
                session, 
                provider="anthropic", 
                model="claude-sonnet-4-6", 
                prompt_tokens=usage.input_tokens, 
                completion_tokens=usage.output_tokens, 
                total_tokens=usage.input_tokens + usage.output_tokens, 
                context_type="classification",
                entity_id=tx.get("entity_id")
            )
        except Exception as e:
            logger.error("Failed to log AI usage", error=str(e))

        return {
            "status": status,
            "method": "ai",
            "reason": ai_data.get("reasoning", "AI classified"),
            "account_id": ai_data.get("account_id") if status == "ai_suggested" else None,
            "property_id": ai_data.get("property_id") if status == "ai_suggested" else None,
            "confidence": confidence,
            "ai_raw": ai_data
        }

    except Exception as e:
        error_msg = str(e)
        method = "ai"
        reason = f"AI Error: {error_msg}"
        
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            method = "ai"
            reason = "AI Quota Exhausted: Flagged for manual review"
        elif "403" in error_msg or "PERMISSION_DENIED" in error_msg:
            method = "ai"
            reason = "AI Permission Denied: Flagged for manual review"
            
        return {
            "status": "pending_review",
            "method": method,
            "reason": reason,
            "ai_error": error_msg
        }

async def reinforce_rule(session: AsyncSession, vendor_name: str, account_id: UUID, property_id: Optional[UUID] = None):
    """
    Creates or updates a vendor_rule based on manual human correction.
    - If rule exists, increment confidence or update account.
    - If new, create with 'learning_loop' source.
    """
    if not vendor_name:
        return

    # Normalize vendor for rule pattern
    pattern = vendor_name.upper().strip()

    # 1. Look for existing rule
    query = text("""
        SELECT id, confidence FROM vendor_rules 
        WHERE pattern = :pattern AND match_type = 'contains'
        LIMIT 1
    """)
    res = await session.execute(query, {"pattern": pattern})
    rule = res.fetchone()
    
    if rule:
        # Update existing rule
        await session.execute(text("""
            UPDATE vendor_rules 
            SET account_id = :acc_id, 
                default_property_id = COALESCE(:prop_id, default_property_id),
                confidence = LEAST(confidence + 0.05, 1.0),
                updated_at = NOW()
            WHERE id = :rid
        """), {"acc_id": account_id, "prop_id": property_id, "rid": rule.id})
        logger.info("Reinforced existing rule", pattern=pattern, rule_id=str(rule.id))
    else:
        # Create new rule
        await session.execute(text("""
            INSERT INTO vendor_rules (pattern, account_id, default_property_id, confidence, property_attribution, match_type, source)
            VALUES (:pattern, :acc_id, :prop_id, 0.90, :attr, 'contains', 'ai_correction')
        """), {
            "pattern": pattern, 
            "acc_id": account_id, 
            "prop_id": property_id,
            "attr": 'direct' if property_id else 'requires_review'
        })
        logger.info("Created new rule from learning loop", pattern=pattern)

async def log_llm_usage(
    session: AsyncSession, 
    provider: str, 
    model: str, 
    prompt_tokens: int, 
    completion_tokens: int, 
    total_tokens: int, 
    context_type: str, 
    entity_id: Optional[Any] = None
):
    """Logs LLM token usage for spend monitoring."""
    # Cost estimation (placeholder rates)
    rates = {
        "gemini-1.5-flash": 0.0000001, # $0.10 per million
        "gpt-4o-mini": 0.00000015,
        "claude-sonnet-4-6": 0.000003, # $3.00 per million input (est)
    }
    rate = rates.get(model, 0)
    cost = total_tokens * rate

    await session.execute(
        text("""
            INSERT INTO llm_usage_log (
                provider, model, prompt_tokens, completion_tokens, total_tokens, cost_est, context_type, entity_id
            ) VALUES (
                :provider, :model, :pt, :ct, :tt, :cost, :ctx, :eid
            )
        """),
        {
            "provider": provider, "model": model, "pt": prompt_tokens, "ct": completion_tokens, 
            "tt": total_tokens, "cost": cost, "ctx": context_type, "eid": entity_id
        }
    )

