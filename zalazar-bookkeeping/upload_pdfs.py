import requests
import glob
import time

files = glob.glob(r'C:\Users\YM\Desktop\AI_BookKeeping_JuanZalazar\Lima*.pdf')
url = "http://localhost:8000/bank-accounts/upload-global"

for f in files:
    print(f"Uploading {f}...")
    with open(f, 'rb') as file_data:
        res = requests.post(url, files={'file': file_data})
        print(res.status_code, res.text)
    time.sleep(2) # Give it a moment to avoid overwhelming
