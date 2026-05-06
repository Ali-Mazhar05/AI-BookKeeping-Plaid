import os
import json
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

def extract():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        print("SUPABASE_URL or SUPABASE_KEY not found in .env")
        return

    supabase: Client = create_client(url, key)
    
     
    #original tables in database
    tables = [
        "accounts",
        "audit_log",
        "bank_accounts",
        "entities",
        "escrow_movements",
        "generated_reports",
        "monthly_property_pnl",
        "notification_log",
        "notification_settings",
        "properties",
        "reconciliation_log",
        "source_documents",
        "transaction_allocations",
        "transactions",
        "vendor_rules"
    ]

    with open("database_extract.txt", "w", encoding="utf-8") as f:
        f.write("DATABASE EXTRACTION (VIA SUPABASE CLIENT)\n")
        f.write("=========================================\n\n")

        for table in tables:
            print(f"Extracting table: {table}")
            f.write(f"TABLE: {table}\n")
            f.write("-" * (len(table) + 7) + "\n")
            
            try:
                # Note: .execute() is required for older versions, 
                # but newer versions might use it differently.
                # In verify_supabase.py it was used.
                res = supabase.table(table).select("*").execute()
                data = res.data
                
                if not data:
                    f.write("  (No records found)\n")
                else:
                    f.write(f"  Records: {len(data)}\n\n")
                    # Header
                    headers = data[0].keys()
                    f.write("  " + " | ".join(headers) + "\n")
                    f.write("  " + "-" * 80 + "\n")
                    for row in data:
                        f.write("  " + " | ".join(str(row.get(h, "")) for h in headers) + "\n")
            except Exception as e:
                print(f"  Error extracting {table}: {e}")
                f.write(f"  Error: {e}\n")
            
            f.write("\n" + "="*40 + "\n\n")

    print("Extraction complete. Saved to database_extract.txt")

if __name__ == "__main__":
    extract()
