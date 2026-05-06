import sys
import os
from pathlib import Path

# Add src to sys.path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from zalazar.plaid.client import get_plaid_client
from zalazar.config import settings
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.country_code import CountryCode

def test_plaid_connectivity():
    print(f"Testing Plaid keys in environment: {settings.PLAID_ENV}")
    client = get_plaid_client()
    
    try:
        # Try to create a simple link token to verify credentials
        request = LinkTokenCreateRequest(
            products=[Products("transactions")],
            client_name="Zalazar Holdings LLC Test",
            country_codes=[CountryCode("US")],
            language="en",
            user=LinkTokenCreateRequestUser(client_user_id="test_user_id")
        )
        response = client.link_token_create(request)
        print("SUCCESS: Plaid credentials are valid!")
        print(f"Link Token created: {response['link_token'][:20]}...")
    except Exception as e:
        print("ERROR: Plaid connectivity test failed.")
        print(f"Details: {str(e)}")
        # Check if it's a 401/403 or similar
        sys.exit(1)

if __name__ == "__main__":
    test_plaid_connectivity()
