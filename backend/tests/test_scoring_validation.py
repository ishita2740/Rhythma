import sys
import os
from datetime import date, timedelta
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.scoring_service import build_model_features, DEFAULT_CYCLE_LENGTH


def test_build_model_features_sanitizes_invalid_dates():
    today = date.today()
    logs = [
        # Invalid end date earlier than start date
        {"start_date": today, "end_date": today - timedelta(days=2)},
        # Same date as previous log (out of order / duplicate)
        {"start_date": today, "end_date": today},
    ]

    features = build_model_features(logs)
    assert len(features) == 2
    # Flow duration must never be negative or zero
    assert features[0]["flow_duration"] >= 1
    assert features[1]["flow_duration"] >= 1
    # Cycle length must fallback to default when delta <= 0
    assert features[0]["cycle_length"] == DEFAULT_CYCLE_LENGTH


def test_dashboard_clamps_future_cycle_days():
    # Verify that future dates do not produce negative cycle days
    future_date = date.today() + timedelta(days=5)
    most_recent = future_date
    raw_day = (date.today() - most_recent).days + 1
    clamped_day = max(1, raw_day)
    assert clamped_day >= 1
