import asyncio
import sys
import argparse
from decimal import Decimal
from zalazar.db import AsyncSessionLocal
from zalazar.mortgage import split_mortgage_transaction

async def main():
    parser = argparse.ArgumentParser(description="Manual mortgage split CLI")
    parser.add_argument("--tx-id", required=True, help="Transaction UUID to split")
    parser.add_argument("--property-id", required=True, help="Property UUID to allocate to")
    parser.add_argument("--interest", required=True, type=Decimal, help="Interest amount")
    parser.add_argument("--principal", required=True, type=Decimal, help="Principal amount")
    parser.add_argument("--escrow", default=Decimal('0.00'), type=Decimal, help="Escrow amount")
    parser.add_argument("--loan-acc", help="Optional loan account number")
    
    args = parser.parse_args()
    
    async with AsyncSessionLocal() as session:
        try:
            await split_mortgage_transaction(
                session=session,
                transaction_id=args.tx_id,
                property_id=args.property_id,
                interest=args.interest,
                principal=args.principal,
                escrow=args.escrow,
                loan_account_number=args.loan_acc
            )
            print("Successfully split mortgage transaction.")
        except Exception as e:
            print(f"Error: {str(e)}")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
