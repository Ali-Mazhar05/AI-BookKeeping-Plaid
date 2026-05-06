import requests
import uuid

API_BASE = 'http://localhost:8000'
ENTITY_ID = '46c637aa-7d06-4f32-8e1b-b4dbec017ecc'

def test_upload():
    # 1. Get accounts
    res = requests.get(f"{API_BASE}/bank-accounts?entity_id={ENTITY_ID}")
    accounts = res.json().get('data', [])
    if not accounts:
        print("No accounts found")
        return
    
    acc_id = accounts[0]['id']
    print(f"Testing upload for account {acc_id}")
    
    # 2. Create a dummy PDF
    dummy_pdf = "test_upload.pdf"
    with open(dummy_pdf, "wb") as f:
        f.write(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF")
    
    # 3. Upload
    with open(dummy_pdf, "rb") as f:
        files = {'file': (dummy_pdf, f, 'application/pdf')}
        res = requests.post(f"{API_BASE}/bank-accounts/{acc_id}/upload-statement", files=files)
    
    print(f"Status Code: {res.status_code}")
    print(f"Response: {res.text}")

if __name__ == "__main__":
    test_upload()
