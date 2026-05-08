"""Unit tests for zalazar.notifier.sms."""
from unittest.mock import MagicMock, patch

import pytest


class TestSmsSend:
    async def test_returns_mock_id_when_unconfigured(self):
        import zalazar.notifier.sms as sms_module
        with patch.object(sms_module, "settings") as mock_cfg:
            mock_cfg.RC_CLIENT_ID = None
            mock_cfg.RC_JWT = None
            result = await sms_module.send("+15551234567", "Test message")
        assert result.startswith("mock_rc_sms_")

    async def test_returns_mock_id_when_jwt_missing(self):
        import zalazar.notifier.sms as sms_module
        with patch.object(sms_module, "settings") as mock_cfg:
            mock_cfg.RC_CLIENT_ID = "some-id"
            mock_cfg.RC_JWT = None
            result = await sms_module.send("+15551234567", "Test message")
        assert result.startswith("mock_rc_sms_")

    async def test_calls_ringcentral_sdk_when_configured(self):
        import zalazar.notifier.sms as sms_module

        fake_secret = MagicMock()
        fake_secret.get_secret_value.return_value = "rc-secret"
        fake_jwt = MagicMock()
        fake_jwt.get_secret_value.return_value = "rc-jwt"

        mock_sdk_instance = MagicMock()
        mock_platform = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value.id = "rc_msg_12345"
        mock_platform.post.return_value = mock_response
        mock_sdk_instance.platform.return_value = mock_platform

        with patch.object(sms_module, "settings") as mock_cfg, \
             patch("zalazar.notifier.sms.SDK", return_value=mock_sdk_instance) as mock_sdk_cls, \
             patch("zalazar.notifier.sms.asyncio.to_thread", side_effect=lambda fn: fn()) as _:

            mock_cfg.RC_CLIENT_ID = "test-id"
            mock_cfg.RC_CLIENT_SECRET = fake_secret
            mock_cfg.RC_SERVER_URL = "https://platform.devtest.ringcentral.com"
            mock_cfg.RC_JWT = fake_jwt
            mock_cfg.RC_FROM_NUMBER = "+15550000000"

            result = await sms_module.send("+15551234567", "Hello")

        assert result == "rc_msg_12345"
        mock_sdk_cls.assert_called_once()
        mock_platform.login.assert_called_once_with(jwt="rc-jwt")
        mock_platform.post.assert_called_once()

    async def test_raises_on_sdk_error(self):
        import zalazar.notifier.sms as sms_module

        fake_secret = MagicMock()
        fake_secret.get_secret_value.return_value = "rc-secret"
        fake_jwt = MagicMock()
        fake_jwt.get_secret_value.return_value = "rc-jwt"

        with patch.object(sms_module, "settings") as mock_cfg, \
             patch("zalazar.notifier.sms.asyncio.to_thread",
                   side_effect=RuntimeError("RingCentral unavailable")):

            mock_cfg.RC_CLIENT_ID = "test-id"
            mock_cfg.RC_CLIENT_SECRET = fake_secret
            mock_cfg.RC_JWT = fake_jwt

            with pytest.raises(RuntimeError, match="RingCentral unavailable"):
                await sms_module.send("+15551234567", "Hello")

    async def test_mock_id_is_unique_per_call(self):
        import zalazar.notifier.sms as sms_module
        with patch.object(sms_module, "settings") as mock_cfg:
            mock_cfg.RC_CLIENT_ID = None
            mock_cfg.RC_JWT = None
            id1 = await sms_module.send("+15550000001", "msg1")
            id2 = await sms_module.send("+15550000002", "msg2")
        assert id1 != id2
