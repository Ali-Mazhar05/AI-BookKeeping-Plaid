from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

def find_working_model():
    api_key = os.getenv('GEMINI_API_KEY')
    client = genai.Client(api_key=api_key)
    
    models = client.models.list()
    for m in models:
        # Only test models that look like generation models
        if "embedding" in m.name or "aqa" in m.name or "imagen" in m.name or "veo" in m.name:
            continue
            
        print(f"Testing {m.name}...")
        try:
            response = client.models.generate_content(model=m.name, contents="hi")
            print(f" SUCCESS: {m.name} is working!")
            return m.name
        except Exception as e:
            if "429" in str(e):
                print(f"  FAIL: {m.name} - Quota exhausted (429)")
            elif "403" in str(e):
                print(f"  FAIL: {m.name} - Permission denied (403)")
            else:
                print(f"  FAIL: {m.name} - {str(e)[:50]}...")
    
    return None

if __name__ == "__main__":
    find_working_model()
