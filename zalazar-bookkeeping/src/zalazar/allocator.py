from typing import List, Dict, Any
from decimal import Decimal, ROUND_HALF_EVEN
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import structlog

logger = structlog.get_logger()

async def allocate(session: AsyncSession, tx: Dict[str, Any], classification: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Produces transaction_allocations rows whose amounts sum to tx.amount.
    """
    amount = Decimal(str(tx['amount']))
    rule = classification.get('rule')
    
    # Layer 2: Vendor Rules (from classification)
    if rule and rule['property_attribution'] == 'direct' and rule['default_property_id']:
        return [{
            "property_id": rule['default_property_id'],
            "amount": amount,
            "method": "direct",
            "confidence": 0.95
        }]
        
    elif rule and rule['property_attribution'] == 'even_split':
        result = await session.execute(
            text("SELECT id FROM properties WHERE entity_id = :entity_id AND is_active = TRUE"),
            {"entity_id": tx['entity_id']}
        )
        property_ids = [row.id for row in result.fetchall()]
        
        if not property_ids:
            logger.warning("No active properties found for even_split", entity_id=tx['entity_id'])
            return []
            
        n = len(property_ids)
        per = (amount / n).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)
        
        allocations = []
        for pid in property_ids:
            allocations.append({
                "property_id": pid,
                "amount": per,
                "percentage": 100 / n,
                "method": "even_split",
                "confidence": 0.95
            })
            
        # Adjust last allocation for rounding residue so sum equals exactly `amount`
        residue = amount - (per * n)
        allocations[-1]["amount"] += residue
        
        return allocations
        
    # Later: Layer 1 (address match) and Layer 3 (bank account default)
    # If no allocations could be made, return empty list.
    return []
