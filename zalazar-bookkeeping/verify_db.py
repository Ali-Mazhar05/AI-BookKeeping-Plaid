import asyncio
import os
import sys
import re

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def get_live_schema():
    async with AsyncSessionLocal() as session:
        result = await session.execute(text(
            "SELECT table_name, column_name "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' "
            "ORDER BY table_name, ordinal_position"
        ))
        rows = result.fetchall()
        schema = {}
        for table, column in rows:
            if table not in schema:
                schema[table] = []
            schema[table].append(column)
        return schema

def get_sql_tables(file_path):
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Simple regex to find CREATE TABLE statements
    tables = re.findall(r'CREATE TABLE IF NOT EXISTS (\w+)', content, re.IGNORECASE)
    return set(tables)

async def verify():
    print("Fetching live schema from Supabase...")
    live_schema = await get_live_schema()
    
    print("Reading db.sql...")
    sql_tables = get_sql_tables("db.sql")
    
    print("\n=== Verification Report ===")
    
    live_tables = set(live_schema.keys())
    
    # Tables in SQL but not in Live
    missing_in_live = sql_tables - live_tables
    if missing_in_live:
        print(f"[-] Tables in db.sql but NOT in Live DB: {missing_in_live}")
    else:
        print("[+] All tables in db.sql exist in the Live DB.")
        
    # Tables in Live but not in SQL
    extra_in_live = live_tables - sql_tables
    # Filter out common Postgres/Supabase tables if any leaked into public
    extra_in_live = {t for t in extra_in_live if not t.startswith('_')}
    
    if extra_in_live:
        print(f"[!] Tables in Live DB but NOT in db.sql: {extra_in_live}")
    else:
        print("[+] No extra tables found in the Live DB.")

    # Check columns for matching tables
    print("\nChecking columns for matching tables...")
    for table in sql_tables & live_tables:
        # Re-parse db.sql for this specific table's columns (very basic check)
        with open("db.sql", 'r') as f:
            content = f.read()
            # Find the table block
            table_match = re.search(f'CREATE TABLE IF NOT EXISTS {table}\s*\((.*?)\);', content, re.DOTALL | re.IGNORECASE)
            if table_match:
                col_lines = table_match.group(1).split('\n')
                sql_cols = []
                for line in col_lines:
                    line = line.strip()
                    if line and not line.startswith('--') and not line.startswith('PRIMARY KEY') and not line.startswith('FOREIGN KEY') and not line.startswith('UNIQUE') and not line.startswith('CONSTRAINT') and not line.startswith('CHECK'):
                        col_name = line.split()[0].replace('"', '')
                        if col_name.upper() not in ['PRIMARY', 'FOREIGN', 'UNIQUE', 'CONSTRAINT', 'CHECK', 'REFERENCES']:
                            sql_cols.append(col_name)
                
                live_cols = live_schema[table]
                
                # Check if all SQL columns are in Live
                missing_cols = set(sql_cols) - set(live_cols)
                if missing_cols:
                    print(f"[!] Table '{table}': Missing columns in Live DB: {missing_cols}")
                else:
                    pass # print(f"[+] Table '{table}': All columns match.")

if __name__ == "__main__":
    asyncio.run(verify())
