import sys
from unittest.mock import MagicMock

import pytest
from unittest.mock import patch
from test_auth import client, mock_auth_dependencies
import firebase_admin.auth
from services.rate_limit_service import RateLimitService

@pytest.fixture
def auth_headers(mock_auth_dependencies):
    RateLimitService.clear_all()

    firebase_admin.auth.verify_id_token.return_value = {
        "phone_number": "+1234567890",
        "uid": "firebase_uid"
    }

    token_response = client.post(
        "/api/v1/auth/firebase-login",
        json={"id_token": "valid_token"},
        headers={"X-Client-Platform": "mobile"}
    )

    token = token_response.json()["access_token"]

    RateLimitService.clear_all()

    return {"Authorization": f"Bearer {token}"}

def test_get_sms_settings_success(auth_headers):
    response = client.get("/api/v1/sms/settings", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {
        "phoneNumber": "+1234567890",
        "enabled": False,
    }

def test_save_sms_settings_success(auth_headers):
    payload = {"phoneNumber": "+1234567890", "enabled": True}
    response = client.post("/api/v1/sms/settings", json=payload, headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"phoneNumber": "+1234567890", "enabled": True}

def test_save_sms_settings_validation_failure(auth_headers):
    payload = {"phoneNumber": "123", "enabled": True}
    response = client.post("/api/v1/sms/settings", json=payload, headers=auth_headers)
    assert response.status_code == 400
    assert "E.164 format" in response.json()["detail"]
    
    payload = {"enabled": True}
    response = client.post("/api/v1/sms/settings", json=payload, headers=auth_headers)
    assert response.status_code == 400
    assert "phone number is required" in response.json()["detail"]

@pytest.fixture
def sms_enabled_headers(auth_headers):
    """An account that has actually switched SMS summaries on.

    ``POST /sms/send-summary`` now refuses when the toggle is off
    (issue #532) — it used to consult it on neither path, so "off" and
    "on" sent the same message. These tests were written against the old
    behaviour and are about Twilio, not about the toggle, so they turn it
    on the way a user does: through the settings endpoint.
    """
    client.post(
        "/api/v1/sms/settings",
        json={"phoneNumber": "+1234567890", "enabled": True},
        headers=auth_headers,
    )
    RateLimitService.clear_all()
    return auth_headers


@patch("api.sms.os.getenv")
@patch("twilio.rest.Client")
def test_send_summary_success(MockClient, mock_getenv, sms_enabled_headers):

    def side_effect(key):
        if key == "TWILIO_ACCOUNT_SID": return "sid"
        if key == "TWILIO_AUTH_TOKEN": return "token"
        if key == "TWILIO_PHONE_NUMBER": return "+1098765432"
        return None
    mock_getenv.side_effect = side_effect
    
    mock_client_instance = MagicMock()
    MockClient.return_value = mock_client_instance
    mock_client_instance.messages.create.return_value = MagicMock(sid="mock-sid")
    
    payload = {"phone_number": "+1234567890", "message": "Test summary"}
    response = client.post("/api/v1/sms/send-summary", json=payload, headers=sms_enabled_headers)
    
    assert response.status_code == 200
    assert response.json()["message"] == "SMS sent successfully"

@patch("api.sms.os.getenv")
@patch("twilio.rest.Client")
def test_send_summary_provider_failure(MockClient, mock_getenv, sms_enabled_headers):

    def side_effect(key):
        if key == "TWILIO_ACCOUNT_SID": return "sid"
        if key == "TWILIO_AUTH_TOKEN": return "token"
        if key == "TWILIO_PHONE_NUMBER": return "+1098765432"
        return None
    mock_getenv.side_effect = side_effect
    
    mock_client_instance = MagicMock()
    MockClient.return_value = mock_client_instance
    mock_client_instance.messages.create.side_effect = Exception("Twilio down")
    
    payload = {"phone_number": "+1234567890", "message": "Test summary"}
    response = client.post("/api/v1/sms/send-summary", json=payload, headers=sms_enabled_headers)
    
    assert response.status_code == 500
    assert "Failed to send SMS" in response.json()["detail"]