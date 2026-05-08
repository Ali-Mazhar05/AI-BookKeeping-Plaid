"""Unit tests for zalazar.plaid.webhooks.handle_webhook."""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

ENTITY_ID = uuid4()
ACCOUNT_ID = uuid4()
ITEM_ID = "plaid_item_abc123"


def _make_account_row(entity_id=ENTITY_ID, account_id=ACCOUNT_ID):
    row = MagicMock()
    row.id = account_id
    row.entity_id = entity_id
    row.bank_name = "Chase"
    row.account_name = "Checking"
    return row


def _make_session(account_row=None):
    """AsyncSession mock that returns an account on the first execute call."""
    session = AsyncMock()
    result = MagicMock()
    result.fetchone.return_value = account_row
    session.execute.return_value = result
    return session


# Patch the module-level plaid client so importing webhooks doesn't fail.
@pytest.fixture(autouse=True)
def patch_plaid_client():
    with patch("zalazar.plaid.webhooks.client", MagicMock()):
        yield


class TestHandleWebhook:
    async def test_ignores_non_transactions_webhook(self):
        from zalazar.plaid.webhooks import handle_webhook
        session = _make_session()
        payload = {"webhook_type": "INCOME", "webhook_code": "PRODUCT_READY", "item_id": ITEM_ID}
        await handle_webhook(session, payload)
        session.execute.assert_not_called()

    async def test_returns_early_for_unknown_item_id(self):
        from zalazar.plaid.webhooks import handle_webhook
        session = _make_session(account_row=None)
        payload = {"webhook_type": "TRANSACTIONS", "webhook_code": "DEFAULT_UPDATE", "item_id": "unknown-item"}
        with patch("zalazar.plaid.webhooks.dispatch") as mock_dispatch:
            await handle_webhook(session, payload)
        mock_dispatch.send.assert_not_called()

    async def test_item_login_required_sends_notification(self):
        from zalazar.plaid.webhooks import handle_webhook
        account = _make_account_row()
        session = _make_session(account_row=account)

        payload = {"webhook_type": "TRANSACTIONS", "webhook_code": "ITEM_LOGIN_REQUIRED", "item_id": ITEM_ID}

        with patch("zalazar.plaid.webhooks.dispatch") as mock_dispatch:
            mock_dispatch.send = AsyncMock()
            mock_dispatch.get_dashboard_url.return_value = "http://localhost:5173/"
            await handle_webhook(session, payload)

        mock_dispatch.send.assert_awaited_once()
        call_kwargs = mock_dispatch.send.call_args.kwargs
        assert call_kwargs["entity_id"] == ENTITY_ID
        assert call_kwargs["channel"] == "both"

    async def test_item_login_required_deactivates_account(self):
        from zalazar.plaid.webhooks import handle_webhook
        account = _make_account_row()
        session = _make_session(account_row=account)

        payload = {"webhook_type": "TRANSACTIONS", "webhook_code": "ITEM_LOGIN_REQUIRED", "item_id": ITEM_ID}

        with patch("zalazar.plaid.webhooks.dispatch") as mock_dispatch:
            mock_dispatch.send = AsyncMock()
            mock_dispatch.get_dashboard_url.return_value = "http://localhost:5173/"
            await handle_webhook(session, payload)

        # Should have executed an UPDATE to set is_active = FALSE
        executed_sqls = [str(call.args[0]) for call in session.execute.call_args_list]
        assert any("is_active" in sql or "UPDATE" in sql.upper() for sql in executed_sqls)

    async def test_user_permission_revoked_sends_notification(self):
        from zalazar.plaid.webhooks import handle_webhook
        account = _make_account_row()
        session = _make_session(account_row=account)

        payload = {"webhook_type": "TRANSACTIONS", "webhook_code": "USER_PERMISSION_REVOKED", "item_id": ITEM_ID}

        with patch("zalazar.plaid.webhooks.dispatch") as mock_dispatch:
            mock_dispatch.send = AsyncMock()
            mock_dispatch.get_dashboard_url.return_value = "http://localhost:5173/"
            await handle_webhook(session, payload)

        mock_dispatch.send.assert_awaited_once()
        call_kwargs = mock_dispatch.send.call_args.kwargs
        assert call_kwargs["entity_id"] == ENTITY_ID
        assert call_kwargs["channel"] == "both"

    async def test_pending_expiration_does_not_crash(self):
        """PENDING_EXPIRATION handler exists but currently sends no notification (known gap)."""
        from zalazar.plaid.webhooks import handle_webhook
        account = _make_account_row()
        session = _make_session(account_row=account)

        payload = {"webhook_type": "TRANSACTIONS", "webhook_code": "PENDING_EXPIRATION", "item_id": ITEM_ID}

        # Should not raise
        with patch("zalazar.plaid.webhooks.dispatch") as mock_dispatch:
            mock_dispatch.send = AsyncMock()
            await handle_webhook(session, payload)

    async def test_sync_updates_available_triggers_sync(self):
        from zalazar.plaid.webhooks import handle_webhook
        account = _make_account_row()
        session = _make_session(account_row=account)

        payload = {"webhook_type": "TRANSACTIONS", "webhook_code": "SYNC_UPDATES_AVAILABLE", "item_id": ITEM_ID}

        with patch("zalazar.plaid.webhooks.asyncio") as mock_asyncio, \
             patch("zalazar.plaid.webhooks.sync_account"):
            await handle_webhook(session, payload)
        mock_asyncio.create_task.assert_called_once()
