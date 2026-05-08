"""Unit tests for zalazar.notifier.email."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _smtp_settings(mock_cfg):
    mock_cfg.SMTP_USER = "sender@gmail.com"
    pwd = MagicMock()
    pwd.get_secret_value.return_value = "smtp-pass"
    mock_cfg.SMTP_PASSWORD = pwd
    mock_cfg.SMTP_SERVER = "smtp.gmail.com"
    mock_cfg.SMTP_PORT = 587


def _no_smtp_settings(mock_cfg):
    mock_cfg.SMTP_USER = None
    mock_cfg.SMTP_PASSWORD = None


def _gmail_settings(mock_cfg):
    mock_cfg.GMAIL_CLIENT_ID = "gmail-client-id"
    secret = MagicMock()
    secret.get_secret_value.return_value = "gmail-secret"
    mock_cfg.GMAIL_CLIENT_SECRET = secret
    token = MagicMock()
    token.get_secret_value.return_value = "gmail-refresh-token"
    mock_cfg.GMAIL_REFRESH_TOKEN = token


def _no_gmail_settings(mock_cfg):
    mock_cfg.GMAIL_CLIENT_ID = None
    mock_cfg.GMAIL_CLIENT_SECRET = None
    mock_cfg.GMAIL_REFRESH_TOKEN = None


class TestEmailSend:
    async def test_returns_mock_id_when_nothing_configured(self):
        import zalazar.notifier.email as email_module
        with patch.object(email_module, "settings") as mock_cfg:
            _no_smtp_settings(mock_cfg)
            _no_gmail_settings(mock_cfg)
            result = await email_module.send("user@test.com", "Subject", "Body")
        assert result.startswith("mock_email_")

    async def test_mock_ids_are_unique(self):
        import zalazar.notifier.email as email_module
        with patch.object(email_module, "settings") as mock_cfg:
            _no_smtp_settings(mock_cfg)
            _no_gmail_settings(mock_cfg)
            id1 = await email_module.send("a@test.com", "S", "B")
            id2 = await email_module.send("b@test.com", "S", "B")
        assert id1 != id2

    async def test_sends_via_smtp_when_configured(self):
        import zalazar.notifier.email as email_module
        with patch.object(email_module, "settings") as mock_cfg, \
             patch("zalazar.notifier.email.aiosmtplib") as mock_smtp:

            _smtp_settings(mock_cfg)
            mock_smtp.send = AsyncMock()

            result = await email_module.send("user@test.com", "Hello", "Plain body")

        assert result.startswith("smtp_")
        mock_smtp.send.assert_awaited_once()

    async def test_smtp_includes_html_as_multipart(self):
        import zalazar.notifier.email as email_module
        with patch.object(email_module, "settings") as mock_cfg, \
             patch("zalazar.notifier.email.aiosmtplib") as mock_smtp:

            _smtp_settings(mock_cfg)
            mock_smtp.send = AsyncMock()

            await email_module.send("user@test.com", "Subject", "plain", html_body="<b>html</b>")

        call_args = mock_smtp.send.call_args
        msg = call_args[0][0]
        assert msg.get_content_type() == "multipart/alternative"

    async def test_falls_back_to_gmail_api_when_smtp_fails(self):
        import zalazar.notifier.email as email_module

        mock_service = MagicMock()
        mock_service.users.return_value.messages.return_value.send.return_value.execute.return_value = {
            "id": "gmail_abc123"
        }

        with patch.object(email_module, "settings") as mock_cfg, \
             patch("zalazar.notifier.email.aiosmtplib") as mock_smtp, \
             patch("zalazar.notifier.email.Credentials"), \
             patch("zalazar.notifier.email.build", return_value=mock_service):

            _smtp_settings(mock_cfg)
            _gmail_settings(mock_cfg)
            mock_smtp.send = AsyncMock(side_effect=Exception("SMTP connection refused"))

            result = await email_module.send("user@test.com", "Subject", "Body")

        assert result == "gmail_abc123"

    async def test_sends_via_gmail_api_when_smtp_not_configured(self):
        import zalazar.notifier.email as email_module

        mock_service = MagicMock()
        mock_service.users.return_value.messages.return_value.send.return_value.execute.return_value = {
            "id": "gmail_xyz789"
        }

        with patch.object(email_module, "settings") as mock_cfg, \
             patch("zalazar.notifier.email.Credentials"), \
             patch("zalazar.notifier.email.build", return_value=mock_service):

            _no_smtp_settings(mock_cfg)
            _gmail_settings(mock_cfg)

            result = await email_module.send("user@test.com", "Subject", "Body")

        assert result == "gmail_xyz789"

    async def test_gmail_api_raises_when_it_fails(self):
        import zalazar.notifier.email as email_module

        with patch.object(email_module, "settings") as mock_cfg, \
             patch("zalazar.notifier.email.Credentials"), \
             patch("zalazar.notifier.email.build", side_effect=Exception("Auth failed")):

            _no_smtp_settings(mock_cfg)
            _gmail_settings(mock_cfg)

            with pytest.raises(Exception, match="Auth failed"):
                await email_module.send("user@test.com", "Subject", "Body")
