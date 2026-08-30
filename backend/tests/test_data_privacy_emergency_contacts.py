import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(**file**), ".."))

from services.firestore_service import UserService, db

def test_user_delete_cascades_all_user_data():
user_id = "test-cascade-user"

```
# Create user
db.collection("users").document(user_id).set({
    "email": "cascade@example.com",
    "username": "cascade_user",
})

# Create related data
db.collection("cycle_logs").document("log1").set({
    "user_id": user_id,
    "start_date": "2026-08-15",
})

db.collection("emergency_contacts").document("c1").set({
    "user_id": user_id,
    "name": "Mom",
})

db.collection("consents").document("consent1").set({
    "user_id": user_id,
    "consent": True,
})

db.collection("conversations").document(user_id).set({
    "user_id": user_id,
    "messages": [],
})

# Delete user and associated data
UserService.delete_user(user_id)

# Verify all associated data was deleted
assert not db.collection("users").document(user_id).get().exists
assert not db.collection("cycle_logs").document("log1").get().exists
assert not db.collection("emergency_contacts").document("c1").get().exists
assert not db.collection("consents").document("consent1").get().exists
assert not db.collection("conversations").document(user_id).get().exists
```

}
