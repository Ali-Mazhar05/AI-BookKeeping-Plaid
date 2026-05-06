import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

try:
    supabase: Client = create_client(url, key)
    res = supabase.table("bank_accounts").select("id").limit(1).execute()
    print(f"Supabase client connection successful. Records found: {len(res.data)}")
except Exception as e:
    print(f"Supabase client connection failed: {e}")
