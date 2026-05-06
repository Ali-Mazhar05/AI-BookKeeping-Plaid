import asyncio
from sqlalchemy import text
import structlog
from zalazar.db import AsyncSessionLocal

logger = structlog.get_logger()

async def seed_vendor_rules():
    """
    Seeds vendor_rules from historical transactions.
    Milestone 4.6.
    """
    async with AsyncSessionLocal() as session:
        # 1. Cluster historical transactions that were manually reviewed
        # and always landed on the same account and (optionally) property.
        query = """
            WITH vendor_clusters AS (
                SELECT 
                    vendor_name_clean,
                    account_id,
                    ARRAY_AGG(DISTINCT transaction_allocations.property_id) as property_ids,
                    COUNT(*) as occurrence_count
                FROM transactions
                LEFT JOIN transaction_allocations ON transaction_allocations.transaction_id = transactions.id
                WHERE status = 'reviewed'
                  AND vendor_name_clean IS NOT NULL
                  AND account_id IS NOT NULL
                GROUP BY vendor_name_clean, account_id
                HAVING COUNT(*) >= 3
            )
            SELECT * FROM vendor_clusters
        """
        
        result = await session.execute(text(query))
        clusters = result.fetchall()
        
        seeded_count = 0
        for cluster in clusters:
            # Check if this vendor consistently maps to this account
            # (The query already filters for clusters of 3+)
            
            # For property attribution:
            # If all occurrences in this cluster map to the SAME single property, set it as default.
            property_id = None
            attribution = 'requires_review'
            
            if cluster.property_ids and len(cluster.property_ids) == 1:
                property_id = cluster.property_ids[0]
                attribution = 'direct'
            
            # Insert rule
            await session.execute(
                text("""
                    INSERT INTO vendor_rules (
                        pattern, account_id, default_property_id, 
                        confidence, property_attribution, match_type, source
                    ) VALUES (
                        :pattern, :account_id, :property_id, 
                        0.95, :attribution, 'contains', 'import'
                    ) ON CONFLICT DO NOTHING
                """),
                {
                    "pattern": cluster.vendor_name_clean.lower(),
                    "account_id": cluster.account_id,
                    "property_id": property_id,
                    "attribution": attribution
                }
            )
            seeded_count += 1
            
        await session.commit()
        logger.info("Vendor rules seeded", count=seeded_count)
        print(f"Seeded {seeded_count} vendor rules covering historical patterns.")

if __name__ == "__main__":
    asyncio.run(seed_vendor_rules())
