import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as session:
        query = text("""
            SELECT 
                constraint_name, 
                delete_rule 
            FROM 
                information_schema.referential_constraints;
        """)
        res = await session.execute(query)
        for row in res.fetchall():
            print(dict(row._mapping))

if __name__ == "__main__":
    asyncio.run(main())
