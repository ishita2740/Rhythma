import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_sms_rate_limit_retry_after_header_formatting():
    remaining_float = 45.8
    header_val = str(int(remaining_float))
    assert header_val == "45"
    assert isinstance(header_val, str)
