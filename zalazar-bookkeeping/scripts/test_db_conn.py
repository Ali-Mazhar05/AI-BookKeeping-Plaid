import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    url = os.getenv("DATABASE_URL")
    if not url:
        print("DATABASE_URL not found in .env")
        return
        
    try:
        print(f"Connecting to database...")
        conn = await asyncio.wait_for(asyncpg.connect(url), timeout=10.0)
        print("SUCCESS")
        await conn.close()
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(main())
