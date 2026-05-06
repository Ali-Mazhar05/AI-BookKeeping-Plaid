import structlog
import uuid
import base64
import aiosmtplib
from typing import Optional
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from ..config import settings

logger = structlog.get_logger()

async def send(recipient: str, subject: str, body: str, html_body: Optional[str] = None) -> str:
    """Send Email via SMTP or Gmail API."""
    
    # 1. Try SMTP if configured
    if settings.SMTP_USER and settings.SMTP_PASSWORD:
        try:
            logger.info("Attempting to send email via SMTP", to=recipient, user=settings.SMTP_USER)
            
            if html_body:
                msg = MIMEMultipart('alternative')
                msg.attach(MIMEText(body, 'plain'))
                msg.attach(MIMEText(html_body, 'html'))
            else:
                msg = MIMEText(body)
                
            msg['Subject'] = subject
            msg['From'] = settings.SMTP_USER
            msg['To'] = recipient

            await aiosmtplib.send(
                msg,
                hostname=settings.SMTP_SERVER,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USER,
                password=settings.SMTP_PASSWORD.get_secret_value(),
                use_tls=(settings.SMTP_PORT == 465),
                start_tls=(settings.SMTP_PORT == 587 or settings.SMTP_PORT == 25),
            )
            
            msg_id = f"smtp_{uuid.uuid4()}"
            logger.info("Email sent successfully via SMTP", to=recipient, message_id=msg_id)
            return msg_id
        except Exception as e:
            logger.error("Failed to send email via SMTP", error=str(e))
            pass

    # 2. Fallback to Gmail API
    if all([settings.GMAIL_CLIENT_ID, settings.GMAIL_CLIENT_SECRET, settings.GMAIL_REFRESH_TOKEN]) and settings.GMAIL_CLIENT_ID != "your-client-id":
        try:
            creds = Credentials(
                token=None,
                refresh_token=settings.GMAIL_REFRESH_TOKEN.get_secret_value(),
                client_id=settings.GMAIL_CLIENT_ID,
                client_secret=settings.GMAIL_CLIENT_SECRET.get_secret_value(),
                token_uri="https://oauth2.googleapis.com/token",
            )

            service = build('gmail', 'v1', credentials=creds)

            if html_body:
                message = MIMEMultipart('alternative')
                message.attach(MIMEText(body, 'plain'))
                message.attach(MIMEText(html_body, 'html'))
            else:
                message = MIMEText(body)

            message['to'] = recipient
            message['subject'] = subject
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

            result = service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()

            logger.info("Email sent successfully via Gmail API", to=recipient, message_id=result['id'])
            return result['id']

        except Exception as e:
            logger.error("Failed to send email via Gmail API", error=str(e))
            raise

    logger.warning("No email provider configured. Email not sent.", recipient=recipient)
    return f"mock_email_{uuid.uuid4()}"
