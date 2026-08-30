import sys
import os
from datetime import date, timedelta
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.sms import generate_cycle_sms_summary


def test_generate_cycle_sms_summary_formatting():
    # Verify generated SMS summary is a valid string under 160 chars.
    #
    # `test_mock_user_id` has no logs and no profile, so there is nothing
    # to anchor a prediction on. This used to produce "Rhythma Summary:
    # Cycle Day 1/28. Next period expected in ~28 days." — three numbers,
    # none of them measured from this user, presented exactly as they
    # would be for someone with a year of history. Since #483 the
    # no-anchor case says so instead, so the assertions here are on the
    # sender and the length rather than on a countdown that should not
    # exist. The "Cycle Day N/M ... Next period expected" wording is
    # still covered, against a user who actually has history, in
    # test_sms_summary_prediction.py.
    summary = generate_cycle_sms_summary("test_mock_user_id")
    assert isinstance(summary, str)
    assert len(summary) <= 160
    assert summary.startswith("Rhythma")
    assert "Log your last period" in summary


def test_generate_cycle_sms_summary_invents_no_countdown_without_data():
    # The regression this file exists to catch, stated directly: a user
    # with nothing logged must not be texted a number derived from the
    # population default as though it were a measurement of her.
    summary = generate_cycle_sms_summary("test_mock_user_id")
    assert "~" not in summary
    assert "Next period expected" not in summary


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
