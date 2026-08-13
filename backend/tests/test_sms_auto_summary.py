import sys
import os
from datetime import date, timedelta
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.sms import generate_cycle_sms_summary


def test_generate_cycle_sms_summary_formatting():
    # Verify generated SMS summary is valid string under 160 chars
    summary = generate_cycle_sms_summary("test_mock_user_id")
    assert isinstance(summary, str)
    assert len(summary) <= 160
    assert "Rhythma Summary" in summary
    assert "Next period expected" in summary


def test_generate_cycle_sms_summary_includes_disclaimer():
    # Disclaimer must be appended when it fits within the 160-char SMS limit
    summary = generate_cycle_sms_summary("test_mock_user_id")
    assert len(summary) <= 160
    assert "Estimate only, not medical/contraceptive advice." in summary


def test_generate_cycle_sms_summary_never_truncates_disclaimer():
    # If a disclaimer can't fit whole, it must be omitted entirely, never cut off mid-sentence
    summary = generate_cycle_sms_summary("test_mock_user_id")
    if "Estimate only" in summary:
        assert summary.rstrip().endswith("medical/contraceptive advice.")
