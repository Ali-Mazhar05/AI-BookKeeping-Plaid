import json
import re
from typing import Optional, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import structlog
from .config import settings
import anthropic

logger = structlog.get_logger()

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
              (match_type = 'exact'    AND pattern = :vendor)
              OR (match_type = 'contains' AND :vendor ILIKE '%' || pattern || '%')
              OR (match_type = 'regex'    AND :vendor ~* pattern)
          )
        ORDER BY confidence DESC, LENGTH(pattern) DESC
        LIMIT 1
    """
    result = await session.execute(text(query), {"vendor": vendor_clean})
    row = result.fetchone()
    return dict(row._mapping) if row else None


def _extract_json(text: str) -> dict:
    """Robustly pull the first JSON object out of a Claude response."""
    # Strip markdown fences anywhere in the string
    cleaned = re.sub(r'```(?:json)?', '', text).replace('```', '').strip()
    # Find the outermost {...}
    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in AI response: {text[:300]}")
    return json.loads(match.group())


async def classify_transaction(session: AsyncSession, tx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classification state machine:
    1. Internal transfer detection  → excluded
    2. High-confidence vendor rule  → auto_categorized
    3. Claude Sonnet                → ai_suggested (≥0.85) or pending_review (<0.85)
       Account suggestion is stored regardless of confidence so the reviewer
       sees a pre-filled category rather than a blank field.
    """
    vendor_clean = tx.get("vendor_name_clean", "") or tx.get("description_clean", "") or ""

    # ── 1. Transfer detection ────────────────────────────────────────────────
    from .normalizer import is_transfer
    if is_transfer(vendor_clean):
        return {
            "status": "excluded",
            "method": "transfer_logic",
            "reason": "Detected internal transfer pattern",
            "account_id": None,
            "property_id": None,
        }

    # ── 2. Vendor rule ───────────────────────────────────────────────────────
    rule = await match_rule(session, vendor_clean)
    if rule and rule["confidence"] >= 0.95 and rule["account_id"] is not None:
        attr = rule["property_attribution"]
        if attr in ("direct", "even_split"):
            return {
                "status": "auto_categorized",
                "method": "rule",
                "reason": f"Matched vendor rule (confidence {rule['confidence']:.0%})",
                "account_id": rule["account_id"],
                "property_id": rule["default_property_id"] if attr == "direct" else None,
                "rule": rule,
            }
        return {
            "status": "flagged",
            "method": "rule",
            "reason": "Rule matched but property attribution requires manual review",
            "account_id": rule["account_id"],
            "rule": rule,
        }

    # ── 3. AI fallback ───────────────────────────────────────────────────────
    if not client:
        return {
            "status": "pending_review",
            "method": "none",
            "reason": "AI client not initialised — set ANTHROPIC_API_KEY",
        }

    # Fetch chart of accounts and active properties
    acc_rows = (await session.execute(
        text("SELECT id, name, code FROM accounts WHERE is_assignable = TRUE ORDER BY code")
    )).fetchall()
    prop_rows = (await session.execute(
        text("SELECT id, name FROM properties WHERE is_active = TRUE ORDER BY name")
    )).fetchall()

    if not acc_rows:
        logger.warning("classify_transaction: accounts table is empty — seed chart of accounts first")
        return {
            "status": "pending_review",
            "method": "none",
            "reason": "No accounts found in chart of accounts — seed required",
        }

    # Build fast lookup sets for validation
    valid_account_ids = {str(r.id) for r in acc_rows}
    valid_property_ids = {str(r.id) for r in prop_rows}

    accounts_text = "\n".join(f'  {{"id":"{r.id}","code":"{r.code}","name":"{r.name}"}}' for r in acc_rows)
    properties_text = (
        "\n".join(f'  {{"id":"{r.id}","name":"{r.name}"}}' for r in prop_rows)
        if prop_rows else "  (none configured)"
    )

    amount = tx.get("amount", 0)
    direction = "INCOME / DEPOSIT" if float(amount) > 0 else "EXPENSE / PAYMENT"

    system_prompt = (
        "You are an expert real estate bookkeeper. "
        "Your only job is to classify a bank transaction into the correct account and property. "
        "You MUST return a single raw JSON object — no markdown, no explanation, no extra text. "
        "You MUST use an id value copied EXACTLY from the provided lists. "
        "Do NOT invent or modify any UUID."
    )

    user_prompt = f"""Classify this transaction:

Vendor : {vendor_clean or "(unknown)"}
Description: {tx.get("description_clean") or tx.get("description") or "(none)"}
Amount  : {amount} ({direction})
Date    : {tx.get("transaction_date")}
Bank    : {tx.get("account_name", "")}
Plaid category: {tx.get("plaid_category_primary") or "(none)"}

ACCOUNTS (pick one id exactly):
[
{accounts_text}
]

PROPERTIES (pick one id or null):
[
{properties_text}
]

Return ONLY this JSON, nothing else:
{{
  "account_id": "<exact id from ACCOUNTS list>",
  "property_id": "<exact id from PROPERTIES list, or null>",
  "confidence": <0.0-1.0>,
  "reasoning": "<plain English, 10-15 words, no jargon>"
}}"""

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        response_text = response.content[0].text
        logger.debug("AI raw response", vendor=vendor_clean, response=response_text[:300])

        ai_data = _extract_json(response_text)

        raw_account_id = ai_data.get("account_id")
        raw_property_id = ai_data.get("property_id")
        confidence = float(ai_data.get("confidence", 0))

        # Validate UUIDs against what we actually sent — reject hallucinations
        account_id = raw_account_id if raw_account_id in valid_account_ids else None
        property_id = raw_property_id if raw_property_id in valid_property_ids else None

        if raw_account_id and not account_id:
            logger.warning(
                "AI returned unknown account_id — rejected",
                vendor=vendor_clean,
                returned=raw_account_id,
            )

        status = "ai_suggested" if confidence >= 0.85 and account_id else "pending_review"

        # Always store the account suggestion so reviewers see a pre-filled category
        # rather than a blank field (even at lower confidence)
        try:
            await log_llm_usage(
                session,
                provider="anthropic",
                model="claude-sonnet-4-6",
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
                context_type="classification",
                entity_id=tx.get("entity_id"),
            )
        except Exception as log_err:
            logger.warning("Failed to log LLM usage", error=str(log_err))

        return {
            "status": status,
            "method": "ai",
            "reason": ai_data.get("reasoning", "AI classified"),
            "account_id": account_id,
            "property_id": property_id,
            "confidence": confidence,
            "ai_raw": ai_data,
        }

    except Exception as e:
        error_msg = str(e)
        logger.error("AI classification failed", vendor=vendor_clean, error=error_msg)

        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            reason = "AI quota exhausted — queued for manual review"
        elif "403" in error_msg or "PERMISSION_DENIED" in error_msg:
            reason = "AI permission denied — check ANTHROPIC_API_KEY"
        else:
            reason = f"AI error — {error_msg[:120]}"

        return {
            "status": "pending_review",
            "method": "ai",
            "reason": reason,
        }


async def reinforce_rule(
    session: AsyncSession,
    vendor_name: str,
    account_id: UUID,
    property_id: Optional[UUID] = None,
):
    """Creates or updates a vendor_rule from a manual reviewer correction."""
    if not vendor_name:
        return

    pattern = vendor_name.upper().strip()

    res = await session.execute(
        text("SELECT id, confidence FROM vendor_rules WHERE pattern = :p AND match_type = 'contains' LIMIT 1"),
        {"p": pattern},
    )
    rule = res.fetchone()

    if rule:
        await session.execute(
            text("""
                UPDATE vendor_rules
                SET account_id = :acc_id,
                    default_property_id = COALESCE(:prop_id, default_property_id),
                    confidence = LEAST(confidence + 0.05, 1.0),
                    updated_at = NOW()
                WHERE id = :rid
            """),
            {"acc_id": account_id, "prop_id": property_id, "rid": rule.id},
        )
        logger.info("Reinforced vendor rule", pattern=pattern, rule_id=str(rule.id))
    else:
        await session.execute(
            text("""
                INSERT INTO vendor_rules
                    (pattern, account_id, default_property_id, confidence, property_attribution, match_type, source)
                VALUES
                    (:pattern, :acc_id, :prop_id, 0.90, :attr, 'contains', 'ai_correction')
            """),
            {
                "pattern": pattern,
                "acc_id": account_id,
                "prop_id": property_id,
                "attr": "direct" if property_id else "requires_review",
            },
        )
        logger.info("Created vendor rule from correction", pattern=pattern)


async def log_llm_usage(
    session: AsyncSession,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    context_type: str,
    entity_id: Optional[Any] = None,
):
    rates = {
        "claude-sonnet-4-6": 0.000003,
        "claude-haiku-4-5-20251001": 0.00000025,
    }
    cost = total_tokens * rates.get(model, 0)

    await session.execute(
        text("""
            INSERT INTO llm_usage_log
                (provider, model, prompt_tokens, completion_tokens, total_tokens, cost_est, context_type, entity_id)
            VALUES
                (:provider, :model, :pt, :ct, :tt, :cost, :ctx, :eid)
        """),
        {
            "provider": provider, "model": model,
            "pt": prompt_tokens, "ct": completion_tokens, "tt": total_tokens,
            "cost": cost, "ctx": context_type, "eid": entity_id,
        },
    )
