import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.sms import SMSSettings


def test_sms_settings_phone_validation():
    # Valid E.164 phone
    valid_settings = SMSSettings(phoneNumber="+919876543210", enabled=False)
    assert valid_settings.normalized_phone == "+919876543210"

    # Empty phone string allowed
    empty_settings = SMSSettings(phoneNumber="", enabled=False)
    assert empty_settings.normalized_phone is None

    # Invalid phone format is accepted at the model level; validation
    # happens at the endpoint (returns 400 with a helpful message).
    invalid_settings = SMSSettings(phoneNumber="invalid_12345", enabled=False)
    assert invalid_settings.normalized_phone == "invalid_12345"
