"""Unit tests for zalazar.notifier.dispatch."""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

ENTITY_ID = uuid4()
LOG_ID = uuid4()

_LARGE_EXPENSE_CTX = {
    "amount": "1500.00",
    "vendor": "Home Depot",
    "date": "2026-01-01",
    "dashboard_url": "http://localhost:5173",
}
_RECON_CTX = {
    "diff": "100.00",
    "account": "Chase Checking",
    "plaid_balance": "5000.00",
    "calculated_balance": "4900.00",
    "dashboard_url": "http://localhost:5173",
}
_INCOME_CTX = {
    "amount": "500.00",
    "source": "Tenant A",
    "date": "2026-01-01",
    "dashboard_url": "http://localhost:5173",
}
_WEEKLY_CTX = {
    "income": "5000.00",
    "expenses": "3000.00",
    "net": "2000.00",
    "reviewed": 10,
    "pending": 2,
    "dashboard_url": "http://localhost:5173",
}


def _make_session():
    """AsyncSession mock where execute() returns a result with scalar_one() = LOG_ID."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one.return_value = LOG_ID
    result.scalar.return_value = 0
    session.execute.return_value = result
    return session


# ── _is_enabled ───────────────────────────────────────────────────────────────

class TestIsEnabled:
    def test_returns_true_with_no_settings(self):
        from zalazar.notifier.dispatch import _is_enabled
        for t in ["large_expense", "uncategorized", "income_received", "cash_flow_change", "reconciliation_mismatch"]:
            assert _is_enabled(None, t) is True

    def test_returns_true_when_enabled(self):
        from zalazar.notifier.dispatch import _is_enabled
        assert _is_enabled({"notify_large_expense": True}, "large_expense") is True

    def test_returns_false_when_disabled(self):
        from zalazar.notifier.dispatch import _is_enabled
        assert _is_enabled({"notify_large_expense": False}, "large_expense") is False

    def test_reconciliation_mismatch_maps_to_notify_reconciliation_fail(self):
        from zalazar.notifier.dispatch import _is_enabled
        assert _is_enabled({"notify_reconciliation_fail": False}, "reconciliation_mismatch") is False

    def test_weekly_summary_always_enabled(self):
        from zalazar.notifier.dispatch import _is_enabled
        assert _is_enabled({"notify_large_expense": False}, "weekly_summary") is True

    def test_unknown_type_returns_false(self):
        from zalazar.notifier.dispatch import _is_enabled
        # Non-empty dict is truthy, so the mapping lookup runs and returns the default (False)
        assert _is_enabled({"notify_large_expense": True}, "nonexistent_type") is False

    def test_cash_flow_change_maps_correctly(self):
        from zalazar.notifier.dispatch import _is_enabled
        assert _is_enabled({"notify_cash_flow_change": False}, "cash_flow_change") is False


# ── _recipient_for ────────────────────────────────────────────────────────────

class TestRecipientFor:
    def test_sms_uses_settings_recipient(self):
        from zalazar.notifier.dispatch import _recipient_for
        user_settings = {"sms_recipient": "+15559998888", "email_recipient": "a@b.com"}
        assert _recipient_for(user_settings, "sms") == "+15559998888"

    def test_email_uses_settings_recipient(self):
        from zalazar.notifier.dispatch import _recipient_for
        user_settings = {"sms_recipient": "+15559998888", "email_recipient": "user@domain.com"}
        assert _recipient_for(user_settings, "email") == "user@domain.com"

    def test_sms_falls_back_to_global_config(self):
        from zalazar.notifier.dispatch import _recipient_for
        # conftest sets SMS_RECIPIENT=+15551111111
        result = _recipient_for(None, "sms")
        assert result == "+15551111111"

    def test_email_falls_back_to_global_config(self):
        from zalazar.notifier.dispatch import _recipient_for
        result = _recipient_for(None, "email")
        assert result == "test@example.com"

    def test_sms_falls_back_when_settings_recipient_is_none(self):
        from zalazar.notifier.dispatch import _recipient_for
        result = _recipient_for({"sms_recipient": None}, "sms")
        assert result == "+15551111111"

    def test_unknown_channel_returns_empty_string(self):
        from zalazar.notifier.dispatch import _recipient_for
        assert _recipient_for({}, "fax") == ""


# ── render_template ───────────────────────────────────────────────────────────

class TestRenderTemplate:
    def test_renders_large_expense_text(self):
        from zalazar.notifier.dispatch import render_template
        result = render_template("large_expense", _LARGE_EXPENSE_CTX, format="text")
        assert result and isinstance(result, str)

    def test_renders_income_received_text(self):
        from zalazar.notifier.dispatch import render_template
        result = render_template("income_received", _INCOME_CTX, format="text")
        assert result and isinstance(result, str)

    def test_renders_reconciliation_mismatch_text(self):
        from zalazar.notifier.dispatch import render_template
        result = render_template("reconciliation_mismatch", _RECON_CTX, format="text")
        assert result and isinstance(result, str)

    def test_html_returns_none_for_missing_template(self):
        from zalazar.notifier.dispatch import render_template
        result = render_template("totally_unknown_type_xyz", {}, format="html")
        assert result is None

    def test_text_fallback_for_missing_template(self):
        from zalazar.notifier.dispatch import render_template
        result = render_template("totally_unknown_type_xyz", {}, format="text")
        assert isinstance(result, str)

    def test_weekly_summary_text_renders(self):
        from zalazar.notifier.dispatch import render_template
        result = render_template("weekly_summary", _WEEKLY_CTX, format="text")
        assert result and isinstance(result, str)


# ── _subject_for ──────────────────────────────────────────────────────────────

class TestSubjectFor:
    @pytest.mark.parametrize("ntype,expected_fragment", [
        ("large_expense", "Expense"),
        ("reconciliation_mismatch", "Reconciliation"),
        ("income_received", "Income"),
        ("uncategorized", "Review"),
        ("cash_flow_change", "Cash Flow"),
        ("weekly_summary", "Weekly"),
    ])
    def test_known_types_return_non_empty_subject(self, ntype, expected_fragment):
        from zalazar.notifier.dispatch import _subject_for
        subject = _subject_for(ntype, {})
        assert subject and expected_fragment in subject

    def test_unknown_type_returns_generic(self):
        from zalazar.notifier.dispatch import _subject_for
        assert _subject_for("nonexistent", {}) == "System Notification"


# ── _is_throttled ─────────────────────────────────────────────────────────────

class TestIsThrottled:
    async def test_not_throttled_for_non_throttled_type(self):
        from zalazar.notifier.dispatch import _is_throttled
        session = _make_session()
        result = await _is_throttled(session, ENTITY_ID, "weekly_summary")
        assert result is False
        session.execute.assert_not_called()

    async def test_not_throttled_when_count_is_zero(self):
        from zalazar.notifier.dispatch import _is_throttled
        session = _make_session()
        session.execute.return_value.scalar.return_value = 0
        assert await _is_throttled(session, ENTITY_ID, "large_expense") is False

    async def test_throttled_when_recent_notification_exists(self):
        from zalazar.notifier.dispatch import _is_throttled
        session = _make_session()
        session.execute.return_value.scalar.return_value = 1
        assert await _is_throttled(session, ENTITY_ID, "large_expense") is True

    @pytest.mark.parametrize("ntype", ["large_expense", "uncategorized", "cash_flow_change"])
    async def test_all_high_frequency_types_are_throttleable(self, ntype):
        from zalazar.notifier.dispatch import _is_throttled
        session = _make_session()
        session.execute.return_value.scalar.return_value = 2
        assert await _is_throttled(session, ENTITY_ID, ntype) is True


# ── _send_impl ────────────────────────────────────────────────────────────────

class TestSendImpl:
    async def test_returns_early_when_notification_disabled(self):
        from zalazar.notifier.dispatch import _send_impl
        from zalazar.notifier import sms, email

        session = _make_session()
        with patch("zalazar.notifier.dispatch.get_notification_settings", new_callable=AsyncMock,
                   return_value={"notify_large_expense": False}), \
             patch("zalazar.notifier.dispatch._is_throttled", new_callable=AsyncMock, return_value=False), \
             patch.object(sms, "send", new_callable=AsyncMock) as mock_sms, \
             patch.object(email, "send", new_callable=AsyncMock) as mock_email:

            result = await _send_impl(session, ENTITY_ID, "large_expense", "sms", _LARGE_EXPENSE_CTX)

        assert result is None
        mock_sms.assert_not_called()
        mock_email.assert_not_called()
        session.execute.assert_not_called()

    async def test_insert_logged_and_suppressed_when_throttled(self):
        from zalazar.notifier.dispatch import _send_impl
        from zalazar.notifier import sms, email

        session = _make_session()
        with patch("zalazar.notifier.dispatch.get_notification_settings", new_callable=AsyncMock, return_value=None), \
             patch("zalazar.notifier.dispatch._is_throttled", new_callable=AsyncMock, return_value=True), \
             patch.object(sms, "send", new_callable=AsyncMock) as mock_sms, \
             patch.object(email, "send", new_callable=AsyncMock) as mock_email:

            result = await _send_impl(session, ENTITY_ID, "large_expense", "sms", _LARGE_EXPENSE_CTX)

        assert result == LOG_ID
        mock_sms.assert_not_called()
        mock_email.assert_not_called()
        session.execute.assert_called_once()  # INSERT only

    async def test_sms_sent_for_sms_channel(self):
        from zalazar.notifier.dispatch import _send_impl
        from zalazar.notifier import sms, email

        session = _make_session()
        with patch("zalazar.notifier.dispatch.get_notification_settings", new_callable=AsyncMock, return_value=None), \
             patch("zalazar.notifier.dispatch._is_throttled", new_callable=AsyncMock, return_value=False), \
             patch.object(sms, "send", new_callable=AsyncMock, return_value="rc_msg_001") as mock_sms, \
             patch.object(email, "send", new_callable=AsyncMock) as mock_email:

            await _send_impl(session, ENTITY_ID, "large_expense", "sms", _LARGE_EXPENSE_CTX)

        mock_sms.assert_awaited_once()
        mock_email.assert_not_called()

    async def test_email_sent_for_email_channel(self):
        from zalazar.notifier.dispatch import _send_impl
        from zalazar.notifier import sms, email

        session = _make_session()
        with patch("zalazar.notifier.dispatch.get_notification_settings", new_callable=AsyncMock, return_value=None), \
             patch("zalazar.notifier.dispatch._is_throttled", new_callable=AsyncMock, return_value=False), \
             patch.object(sms, "send", new_callable=AsyncMock) as mock_sms, \
             patch.object(email, "send", new_callable=AsyncMock, return_value="gmail_msg_001") as mock_email:

            await _send_impl(session, ENTITY_ID, "weekly_summary", "email", _WEEKLY_CTX)

        mock_email.assert_awaited_once()
        mock_sms.assert_not_called()

    async def test_both_channels_call_sms_and_email(self):
        from zalazar.notifier.dispatch import _send_impl
        from zalazar.notifier import sms, email

        session = _make_session()
        with patch("zalazar.notifier.dispatch.get_notification_settings", new_callable=AsyncMock, return_value=None), \
             patch("zalazar.notifier.dispatch._is_throttled", new_callable=AsyncMock, return_value=False), \
             patch.object(sms, "send", new_callable=AsyncMock, return_value="rc_msg") as mock_sms, \
             patch.object(email, "send", new_callable=AsyncMock, return_value="gmail_msg") as mock_email:

            await _send_impl(session, ENTITY_ID, "reconciliation_mismatch", "both", _RECON_CTX)

        mock_sms.assert_awaited_once()
        mock_email.assert_awaited_once()

    async def test_failure_updates_log_status_to_failed(self):
        from zalazar.notifier.dispatch import _send_impl
        from zalazar.notifier import sms, email

        session = _make_session()
        with patch("zalazar.notifier.dispatch.get_notification_settings", new_callable=AsyncMock, return_value=None), \
             patch("zalazar.notifier.dispatch._is_throttled", new_callable=AsyncMock, return_value=False), \
             patch.object(sms, "send", new_callable=AsyncMock, side_effect=RuntimeError("RC down")), \
             patch.object(email, "send", new_callable=AsyncMock):

            with pytest.raises(RuntimeError, match="RC down"):
                await _send_impl(session, ENTITY_ID, "large_expense", "sms", _LARGE_EXPENSE_CTX)

        # INSERT + failure UPDATE = 2 execute calls minimum
        assert session.execute.call_count >= 2

    async def test_no_sms_when_recipient_is_empty(self):
        from zalazar.notifier.dispatch import _send_impl
        from zalazar.notifier import sms

        session = _make_session()
        with patch("zalazar.notifier.dispatch.get_notification_settings", new_callable=AsyncMock,
                   return_value={"sms_recipient": None}), \
             patch("zalazar.notifier.dispatch._is_throttled", new_callable=AsyncMock, return_value=False), \
             patch("zalazar.notifier.dispatch.settings") as mock_cfg, \
             patch.object(sms, "send", new_callable=AsyncMock) as mock_sms:

            mock_cfg.SMS_RECIPIENT = ""
            mock_cfg.EMAIL_RECIPIENT = ""
            mock_cfg.DASHBOARD_URL = "http://localhost:5173"

            await _send_impl(session, ENTITY_ID, "large_expense", "sms", _LARGE_EXPENSE_CTX)

        mock_sms.assert_not_called()


# ── get_dashboard_url ─────────────────────────────────────────────────────────

class TestGetDashboardUrl:
    def test_base_url_no_path(self):
        from zalazar.notifier.dispatch import get_dashboard_url
        with patch("zalazar.notifier.dispatch.settings") as mock_cfg:
            mock_cfg.DASHBOARD_URL = "http://localhost:5173"
            assert get_dashboard_url() == "http://localhost:5173"

    def test_appends_path(self):
        from zalazar.notifier.dispatch import get_dashboard_url
        with patch("zalazar.notifier.dispatch.settings") as mock_cfg:
            mock_cfg.DASHBOARD_URL = "http://localhost:5173"
            assert get_dashboard_url("/review") == "http://localhost:5173/review"

    def test_strips_double_slashes(self):
        from zalazar.notifier.dispatch import get_dashboard_url
        with patch("zalazar.notifier.dispatch.settings") as mock_cfg:
            mock_cfg.DASHBOARD_URL = "http://localhost:5173/"
            assert get_dashboard_url("/review") == "http://localhost:5173/review"
