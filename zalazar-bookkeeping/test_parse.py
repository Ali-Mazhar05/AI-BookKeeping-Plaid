import asyncio
import os
import json
import sys
# Add the project root to sys.path so we can import src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.zalazar.statements.processor import extract_from_pdf

async def main():
    files = [
        r"C:\Users\YM\Desktop\AI_BookKeeping_JuanZalazar\Lima One Dec 2025  Statement of Account for Loan #119434 (1).pdf",
        r"C:\Users\YM\Desktop\AI_BookKeeping_JuanZalazar\Lima One Nov 2025  Statement of Account for Loan #119434.pdf",
        r"C:\Users\YM\Desktop\AI_BookKeeping_JuanZalazar\Lima One ZH Oct 2025 Statement for loan 9434.pdf"
    ]
    for f in files:
        print(f"Testing {os.path.basename(f)}...")
        try:
            txs = await extract_from_pdf(f)
            print(json.dumps(txs, indent=2))
        except Exception as e:
            print("Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
