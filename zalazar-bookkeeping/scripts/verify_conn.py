import asyncio
import sys
import os

# Add src to sys.path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from zalazar.db import AsyncSessionLocal
from sqlalchemy import text

async def test_db():
    # Try port 5432 and 6543
    ports = [5432, 6543]
    base_url = "postgresql+asyncpg://postgres:Awais9876$&+@db.vlgtkscnskmhzmlkonhz.supabase.co"
    
    for port in ports:
        url = f"{base_url}:{port}/postgres"
        print(f"Trying port {port}...")
        try:
            engine = create_async_engine(url, connect_args={"command_timeout": 10})
            async with engine.begin() as conn:
                result = await conn.execute(text("SELECT 1"))
                print(f"SUCCESS on port {port}: {result.scalar() == 1}")
                return
        except Exception as e:
            print(f"FAILED on port {port}: {type(e).__name__}: {e}")
    
    print("All connection attempts failed.")

if __name__ == "__main__":
    from sqlalchemy.ext.asyncio import create_async_engine
    asyncio.run(test_db())
