from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

load_dotenv()

def check_limits():
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("Error: GEMINI_API_KEY not found in .env")
        return

    client = genai.Client(api_key=api_key)
    
    print("--- Gemini API Diagnostic ---")
    print(f"API Key: {api_key[:10]}...")

    # 1. List Available Models
    print("\n[1] Checking Available Models...")
    try:
        models = client.models.list()
        flash_models = [m.name for m in models if 'flash' in m.name]
        print(f"Found {len(flash_models)} Flash models.")
    except Exception as e:
        print(f"Failed to list models: {e}")
        return

    # 2. Test Token Counting & Usage Metadata
    target_model = "gemini-2.0-flash" # Defaulting to 2.0 as it was in the list
    if "models/gemini-1.5-flash" in flash_models:
        target_model = "gemini-1.5-flash"
    
    print(f"\n[2] Testing Usage Metadata for: {target_model}")
    try:
        chat = client.chats.create(
            model=target_model,
            history=[
                types.Content(role="user", parts=[types.Part(text="Hi my name is Bob")]),
                types.Content(role="model", parts=[types.Part(text="Hi Bob!")]),
            ],
        )

        # Count tokens
        history = chat.get_history()
        tokens = client.models.count_tokens(model=target_model, contents=history)
        print(f"Tokens in history: {tokens.total_tokens}")

        # Send message and get usage
        print("Sending test message...")
        response = chat.send_message(
            message="In one sentence, explain how a computer works to a young child."
        )
        print("\n--- Usage Metadata ---")
        print(f"Prompt Tokens: {response.usage_metadata.prompt_token_count}")
        print(f"Candidates Tokens: {response.usage_metadata.candidates_token_count}")
        print(f"Total Tokens: {response.usage_metadata.total_tokens}")
        print(f"Cached Content Tokens: {response.usage_metadata.cached_content_token_count}")
        
        print("\n--- Response ---")
        print(response.text)

    except Exception as e:
        print(f"\n[ERROR] Generation failed: {e}")
        print("\nNOTE: If you see 'PERMISSION_DENIED' or 'limit: 0', your project quota is restricted.")

if __name__ == "__main__":
    check_limits()
