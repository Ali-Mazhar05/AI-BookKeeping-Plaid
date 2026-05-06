import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from zalazar.notifier import email
from zalazar.config import settings

async def main():
    recipient = "alimazhar3005@gmail.com"
    subject = "Zalazar Bookkeeping - Verification Email"
    body = """
    Hello,
    
    This is a verification email from Zalazar Bookkeeping.
    If you are receiving this, it means your Gmail API integration is working correctly.
    
    Thank you!
    """
    
    print(f"Attempting to send email to {recipient}...")
    try:
        msg_id = await email.send(recipient, subject, body)
        print(f"Success! Message ID: {msg_id}")
        if "mock" in msg_id:
            print("WARNING: Email was mocked. Check your .env for GMAIL_ credentials.")
        else:
            print("Real email sent via Gmail API.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
