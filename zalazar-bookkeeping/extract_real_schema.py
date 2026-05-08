import asyncio
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def extract_complete_schema():
    async with AsyncSessionLocal() as session:
        sql_output = ["-- REAL SCHEMA EXTRACTED FROM LIVE DB", "BEGIN;", ""]
        
        # 1. Extensions
        sql_output.append("-- Extensions")
        sql_output.append("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
        sql_output.append("CREATE EXTENSION IF NOT EXISTS \"pg_trgm\";")
        sql_output.append("CREATE EXTENSION IF NOT EXISTS \"pgcrypto\";")
        sql_output.append("")

        # 2. Enums
        sql_output.append("-- Custom Enums")
        enums_res = await session.execute(text(
            "SELECT t.typname as enum_name, e.enumlabel as enum_value "
            "FROM pg_type t JOIN pg_enum e ON t.oid = e.enumtypid "
            "JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace "
            "WHERE n.nspname = 'public' "
            "ORDER BY enum_name, e.enumsortorder"
        ))
        enums = {}
        for name, value in enums_res.fetchall():
            enums.setdefault(name, []).append(f"'{value}'")
        
        for name, values in enums.items():
            sql_output.append(f"DO $$ BEGIN")
            sql_output.append(f"    CREATE TYPE {name} AS ENUM ({', '.join(values)});")
            sql_output.append(f"EXCEPTION WHEN duplicate_object THEN null; END $$;")
        sql_output.append("")

        # 3. Tables
        tables_res = await session.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE' AND table_name NOT LIKE 'pg_%' AND table_name NOT LIKE 'sql_%'"
        ))
        tables = [r[0] for r in tables_res.fetchall()]
        
        for table in sorted(tables):
            sql_output.append(f"-- Table: {table}")
            sql_output.append(f"CREATE TABLE IF NOT EXISTS {table} (")
            
            # Get Columns
            cols_res = await session.execute(text(
                "SELECT column_name, udt_name, is_nullable, column_default "
                "FROM information_schema.columns "
                f"WHERE table_name = '{table}' AND table_schema = 'public' "
                "ORDER BY ordinal_position"
            ))
            cols = cols_res.fetchall()
            col_defs = []
            for col_name, udt_name, is_null, default in cols:
                # Use udt_name for custom types
                data_type = udt_name if udt_name in enums else udt_name
                if data_type == 'varchar': data_type = 'text'
                if data_type == 'int4': data_type = 'integer'
                if data_type == 'int8': data_type = 'bigint'
                if data_type == 'bool': data_type = 'boolean'
                if data_type == 'timestamptz': data_type = 'timestamp with time zone'
                
                null_str = "NOT NULL" if is_null == "NO" else ""
                def_str = f"DEFAULT {default}" if default else ""
                col_defs.append(f"    {col_name:<20} {data_type:<20} {null_str} {def_str}".strip())
            
            sql_output.append(",\n".join(col_defs))
            
            # Basic Primary Key attempt
            if any(c[0] == 'id' for c in cols):
                sql_output.append("    ,PRIMARY KEY (id)")
                
            sql_output.append(");")
            sql_output.append("")

        sql_output.append("COMMIT;")
        return "\n".join(sql_output)

async def main():
    ddl = await extract_complete_schema()
    with open("db.sql", "w") as f:
        f.write(ddl)
    print("SUCCESS: Comprehensive db.sql generated.")

if __name__ == "__main__":
    asyncio.run(main())
