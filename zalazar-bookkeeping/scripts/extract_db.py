import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

async def extract():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not found in .env")
        return

    print(f"Connecting to: {database_url.split('@')[-1]}") # Print host only for safety
    try:
        conn = await asyncpg.connect(database_url)
        print("Connected successfully.")
        
        # Get tables
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE';
        """)
        print(f"Found {len(tables)} tables.")

        with open("database_extract.txt", "w", encoding="utf-8") as f:
            f.write("DATABASE EXTRACTION\n")
            f.write("===================\n\n")

            for table_record in tables:
                table_name = table_record['table_name']
                print(f"Extracting table: {table_name}")
                f.write(f"TABLE: {table_name}\n")
                f.write("-" * (len(table_name) + 7) + "\n")

                # Get columns
                columns = await conn.fetch("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = $1
                    AND table_schema = 'public'
                    ORDER BY ordinal_position;
                """, table_name)

                f.write("Columns:\n")
                for col in columns:
                    f.write(f"  - {col['column_name']} ({col['data_type']}) | Nullable: {col['is_nullable']} | Default: {col['column_default']}\n")
                
                # Get data
                f.write("\nData:\n")
                try:
                    rows = await conn.fetch(f'SELECT * FROM "{table_name}"')
                    if not rows:
                        f.write("  (No records found)\n")
                    else:
                        # Header
                        headers = rows[0].keys()
                        f.write("  " + " | ".join(headers) + "\n")
                        f.write("  " + "-" * 50 + "\n")
                        for row in rows:
                            f.write("  " + " | ".join(str(val) for val in row.values()) + "\n")
                except Exception as data_e:
                    print(f"Error fetching data for {table_name}: {data_e}")
                    f.write(f"  Error fetching data: {data_e}\n")
                
                f.write("\n" + "="*30 + "\n\n")

        print("Extraction complete. Saved to database_extract.txt")

    except Exception as e:
        print(f"Connection or extraction failed: {e}")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(extract())
