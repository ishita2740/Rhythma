import sys
import os
from datetime import date
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.cycle import CycleLog, CycleLogResponse


def test_cycle_log_response_schema_validation():
    today = date.today()
    log_input = CycleLog(
        start_date=today,
        flow_intensity="medium",
        mood="happy",
        symptoms=["cramps"],
        sleep_hours=7.5,
        stress_level=2,
    )

    response_payload = {
        "message": "Cycle logged successfully",
        "id": "mock-log-123",
        "data": log_input,
    }

    # Validate against CycleLogResponse Pydantic schema
    response_model = CycleLogResponse(**response_payload)
    assert response_model.id == "mock-log-123"
    assert response_model.data.start_date == today
    assert response_model.data.flow_intensity == "medium"
    assert response_model.data.symptoms == ["cramps"]
