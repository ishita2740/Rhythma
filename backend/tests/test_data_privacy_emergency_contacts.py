import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.firestore_service import UserService, db


def test_user_delete_cascades_collections():
    user_id = "test-cascade-user"
    user_data = {"email": "cascade@example.com", "username": "cascade_user"}
    db.collection("users").document(user_id).set(user_data)
    db.collection("emergency_contacts").document("c1").set({"user_id": user_id, "name": "Mom"})
    db.collection("conversations").document(user_id).set({"user_id": user_id, "messages": []})

    UserService.delete_user(user_id)

    assert not db.collection("users").document(user_id).get().exists
    assert not db.collection("conversations").document(user_id).get().exists
