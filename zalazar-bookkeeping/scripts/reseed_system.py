import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

import asyncio
from sqlalchemy import text
from zalazar.db import AsyncSessionLocal

async def seed_new_structure():
    async with AsyncSessionLocal() as session:
        try:
            print("Wiping existing entities, properties, and accounts...")
            # We use cascades or order correctly to avoid FK violations
            await session.execute(text("TRUNCATE transaction_allocations CASCADE"))
            await session.execute(text("TRUNCATE transactions CASCADE"))
            await session.execute(text("TRUNCATE properties CASCADE"))
            await session.execute(text("TRUNCATE bank_accounts CASCADE"))
            await session.execute(text("TRUNCATE entities CASCADE"))
            await session.execute(text("TRUNCATE accounts CASCADE"))
            
            # 1. Seed Entities
            print("Seeding entities...")
            entities = [
                {"name": "Zalazar Holdings", "legal_name": "Zalazar Holdings LLC", "type": "llc"},
                {"name": "607 Ash", "legal_name": "607 Ash LLC", "type": "llc"},
                {"name": "400 Carbon", "legal_name": "400 Carbon LLC", "type": "llc"},
                {"name": "779 Market", "legal_name": "779 Market LLC", "type": "llc"},
                {"name": "1614 Bellevue", "legal_name": "1614 Bellevue LLC", "type": "llc"},
            ]
            entity_map = {}
            for e in entities:
                res = await session.execute(
                    text("INSERT INTO entities (name, legal_name, entity_type) VALUES (:name, :legal_name, :type) RETURNING id"),
                    e
                )
                entity_map[e["name"]] = res.scalar_one()

            # 2. Seed Properties
            print("Seeding properties...")
            properties = [
                {"entity": "Zalazar Holdings", "name": "811 Townsend", "addr": "811 Townsend"},
                {"entity": "Zalazar Holdings", "name": "817 Townsend", "addr": "817 Townsend"},
                {"entity": "Zalazar Holdings", "name": "819 Townsend", "addr": "819 Townsend"},
                {"entity": "607 Ash", "name": "607 Ash", "addr": "607 Ash"},
                {"entity": "400 Carbon", "name": "400 Carbon", "addr": "400 Carbon"},
                {"entity": "779 Market", "name": "779 Market", "addr": "779 Market"},
                {"entity": "1614 Bellevue", "name": "1614 Bellevue", "addr": "1614 Bellevue"},
            ]
            for p in properties:
                await session.execute(
                    text("""
                        INSERT INTO properties (entity_id, name, address, city, state, zip) 
                        VALUES (:eid, :name, :addr, 'Unknown', 'Unknown', '00000')
                    """),
                    {"eid": entity_map[p["entity"]], "name": p["name"], "addr": p["addr"]}
                )

            # 3. Seed Chart of Accounts
            print("Seeding chart of accounts...")
            coa = {
                "income": [
                    "Rental Income", "Late Fees", "Other Income", "Tenant Reimbursements"
                ],
                "operating_expense": [
                    "Advertising / Marketing", "Bank Fees / Merchant Fees", "Cleaning / Turnover",
                    "Contract Labor", "Legal & Professional", "Insurance", "Office / Admin",
                    "Postage / Mailing", "Permits / Licenses", "Property Management",
                    "Repairs & Maintenance", "Supplies", "Utilities - Electric",
                    "Utilities - Gas", "Utilities - Water / Sewer", "Utilities - Internet / Phone",
                    "Travel", "Meals", "Vehicle / Gas", "Software / Subscriptions"
                ],
                "property_cost": [
                    "Mortgage Interest", "Loan Fees / Finance Costs", "Property Taxes", "HOA / Association Dues"
                ],
                "capital_non_expense": [
                    "CapEx / Improvements", "Furniture / Equipment", "Security Deposits Held",
                    "Loan Principal", "Owner Contributions", "Owner Draws"
                ],
                "other": [
                    "Depreciation", "Amortization", "Miscellaneous"
                ]
            }
            
            for acct_type, names in coa.items():
                for i, name in enumerate(names):
                    code = f"{'4' if acct_type=='income' else '6' if acct_type=='operating_expense' else '7' if acct_type=='property_cost' else '1' if acct_type=='capital_non_expense' else '9'}{i+1:02d}"
                    await session.execute(
                        text("""
                            INSERT INTO accounts (code, name, account_type, is_pnl, is_assignable, display_order)
                            VALUES (:code, :name, :type, :is_pnl, TRUE, :order)
                        """),
                        {
                            "code": code,
                            "name": name,
                            "type": acct_type,
                            "is_pnl": acct_type in ['income', 'operating_expense', 'property_cost', 'other'],
                            "order": i
                        }
                    )

            await session.commit()
            print("Successfully re-seeded system structure.")
        except Exception as e:
            await session.rollback()
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(seed_new_structure())
