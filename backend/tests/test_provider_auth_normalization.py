import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.email_identity import normalize_email


def test_provider_email_normalization_consistency():
    raw_email = "  Doctor.Jane@Hospital.COM  "
    normalized = normalize_email(raw_email)
    assert normalized == "doctor.jane@hospital.com"
