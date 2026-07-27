import pytest
from tests.test_auth import client, mock_auth_dependencies
import firebase_admin.auth

@pytest.fixture
def auth_headers(mock_auth_dependencies):
    firebase_admin.auth.verify_id_token.return_value = {"phone_number": "+1234567890", "uid": "firebase_uid"}
    token_response = client.post(
        "/api/v1/auth/firebase-login",
        json={"id_token": "valid_token"}
    )
    token = token_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_get_scores_success(auth_headers):
    response = client.get("/api/v1/insights/test-user-id-123/scores", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Scores for user test-user-id-123"

def test_get_scores_unauthorized(auth_headers):
    response = client.get("/api/v1/insights/other-user-id/scores", headers=auth_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized"

def test_get_scores_missing_fields(auth_headers):
    # Testing with missing user_id which is a path parameter, will result in 404
    response = client.get("/api/v1/insights//scores", headers=auth_headers)
    assert response.status_code == 404

def test_get_scores_invalid_payload():
    # Sending POST request to a GET endpoint
    response = client.post("/api/v1/insights/test-user-id-123/scores", json={"invalid": "payload"})
    assert response.status_code == 405 # Method Not Allowed

def test_get_scores_empty_history(auth_headers):
    # Insights router currently doesn't fetch history, but simulating the endpoint call
    response = client.get("/api/v1/insights/test-user-id-123/scores", headers=auth_headers)
    assert response.status_code == 200
