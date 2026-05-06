import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

def final_extract():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
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

    output_file = "database_complete_extract.txt"
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("=== DATABASE FULL EXTRACT ===\n\n")
        
        f.write("SECTION 1: SCHEMA DEFINITION (SQL)\n")
        f.write("==================================\n")
        migration_dir = "migrations"
        if os.path.exists(migration_dir):
            for sql_file in sorted(os.listdir(migration_dir)):
                if sql_file.endswith(".sql"):
                    f.write(f"\n--- FILE: {sql_file} ---\n")
                    with open(os.path.join(migration_dir, sql_file), "r") as sql_f:
                        f.write(sql_f.read())
                        f.write("\n")
        
        f.write("\n\nSECTION 2: DATA EXTRACT\n")
        f.write("=======================\n")

        for table in tables:
            try:
                res = supabase.table(table).select("*").execute()
                data = res.data
                if data is not None: # Table exists
                    f.write(f"\nTABLE: {table}\n")
                    f.write("-" * (len(table) + 7) + "\n")
                    if not data:
                        f.write("  (No records found)\n")
                    else:
                        f.write(f"  Records: {len(data)}\n")
                        headers = data[0].keys()
                        f.write("  " + " | ".join(headers) + "\n")
                        f.write("  " + "-" * 100 + "\n")
                        for row in data:
                            f.write("  " + " | ".join(str(row.get(h, "")) for h in headers) + "\n")
                    f.write("\n" + "="*50 + "\n")
            except Exception:
                # If table doesn't exist, just skip it or log it
                pass

    print(f"Final extraction complete. Saved to {output_file}")

if __name__ == "__main__":
    final_extract()
