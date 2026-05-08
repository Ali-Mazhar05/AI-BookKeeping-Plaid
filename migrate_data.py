import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import sys
import uuid
import json

# OLD Supabase URL (Source)
OLD_URL = "postgresql+asyncpg://postgres.vlgtkscnskmhzmlkonhz:Awais9876%24%26%2B@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres"

# NEW Supabase URL (Destination) - From your .env
NEW_URL = "postgresql+asyncpg://postgres.qgugpspzvecrqqnldsxm:Juan_Zalazar73@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres"

# List tables in order of dependency (Parents first)
TABLES = [
    "entities", "properties", "accounts", "bank_accounts", 
    "vendor_rules", "transactions", "transaction_allocations",
    "notification_settings", "notification_log", "llm_usage_log"
]

async def migrate():
    connect_args = {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4().hex}__",
    }
    
    source_engine = create_async_engine(OLD_URL, connect_args=connect_args)
    dest_engine = create_async_engine(NEW_URL, connect_args=connect_args)

    print(f"Starting migration from Old -> New...")

    async with source_engine.connect() as s_conn, dest_engine.begin() as d_conn:
        # Disable foreign key checks temporarily if needed, or follow order
        for table in TABLES:
            print(f"Migrating table: {table}...", end=" ")
            
            # 1. Fetch data from source
            result = await s_conn.execute(text(f"SELECT * FROM {table}"))
            rows = result.fetchall()
            
            if not rows:
                print("Empty, skipping.")
                continue

            # 2. Prepare columns and insert
            cols = result.keys()
            col_names = ", ".join(cols)
            placeholders = ", ".join([f":{c}" for c in cols])
            
            # Use ON CONFLICT DO NOTHING to avoid errors if some data exists
            insert_stmt = text(f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING")
            
            count = 0
            for row in rows:
                row_dict = dict(row._mapping)
                # Convert dicts to JSON strings for JSONB columns
                for k, v in row_dict.items():
                    if isinstance(v, dict) or isinstance(v, list):
                        row_dict[k] = json.dumps(v)
                
                await d_conn.execute(insert_stmt, row_dict)
                count += 1
            
            print(f"Done ({count} rows).")

    print("\nMigration Complete!")

if __name__ == "__main__":
    asyncio.run(migrate())
