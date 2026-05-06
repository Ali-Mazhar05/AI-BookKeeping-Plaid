import asyncio
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from zalazar.db import AsyncSessionLocal
from zalazar.reports.dscr import calculate_property_dscr
from datetime import date
import json

async def report():
    props = {
        "811 Townsend": "05a54098-b75a-49c1-8c76-782949ac67c0",
        "817 Townsend": "735df49a-6d28-40de-ac77-206494e1c0fa",
        "819 Townsend": "c9512280-d7ee-4dbf-a1ae-cbec07bf5c1a"
    }
    
    start = date(2025, 10, 1)
    end = date(2025, 10, 31)
    
    async with AsyncSessionLocal() as session:
        results = {}
        for name, pid in props.items():
            res = await calculate_property_dscr(session, pid, start, end)
            results[name] = res
            
        print(json.dumps(results, indent=2))

if __name__ == "__main__":
    asyncio.run(report())
