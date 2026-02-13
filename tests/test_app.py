"""Tests for the Mergington High School API."""

import copy
import pytest
from fastapi.testclient import TestClient

from src.app import app, activities

client = TestClient(app)

# Store original activities state for resetting between tests
_original_activities = copy.deepcopy(activities)


@pytest.fixture(autouse=True)
def reset_activities():
    """Reset the in-memory activities database before each test."""
    for key in activities:
        activities[key] = copy.deepcopy(_original_activities[key])
    # Remove any keys that were added during a test
    for key in list(activities.keys()):
        if key not in _original_activities:
            del activities[key]
    yield


# --- GET / ---

class TestRoot:
    def test_root_redirects_to_static(self):
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/static/index.html"


# --- GET /activities ---

class TestGetActivities:
    def test_get_activities_returns_all(self):
        response = client.get("/activities")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "Soccer Team" in data
        assert "Basketball Team" in data
        assert "Chess Club" in data

    def test_activity_has_expected_fields(self):
        response = client.get("/activities")
        data = response.json()
        activity = data["Soccer Team"]
        assert "description" in activity
        assert "schedule" in activity
        assert "max_participants" in activity
        assert "participants" in activity

    def test_activity_participants_is_list(self):
        response = client.get("/activities")
        data = response.json()
        for name, details in data.items():
            assert isinstance(details["participants"], list), f"{name} participants should be a list"


# --- POST /activities/{activity_name}/signup ---

class TestSignup:
    def test_signup_success(self):
        response = client.post(
            "/activities/Soccer Team/signup?email=newstudent@mergington.edu"
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "newstudent@mergington.edu" in data["message"]

    def test_signup_adds_participant(self):
        client.post("/activities/Soccer Team/signup?email=newstudent@mergington.edu")
        response = client.get("/activities")
        participants = response.json()["Soccer Team"]["participants"]
        assert "newstudent@mergington.edu" in participants

    def test_signup_activity_not_found(self):
        response = client.post(
            "/activities/Nonexistent Club/signup?email=test@mergington.edu"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Activity not found"

    def test_signup_duplicate_returns_400(self):
        # liam@mergington.edu is already in Soccer Team
        response = client.post(
            "/activities/Soccer Team/signup?email=liam@mergington.edu"
        )
        assert response.status_code == 400
        assert "already signed up" in response.json()["detail"].lower()

    def test_signup_does_not_duplicate_participant(self):
        client.post("/activities/Soccer Team/signup?email=liam@mergington.edu")
        response = client.get("/activities")
        participants = response.json()["Soccer Team"]["participants"]
        count = participants.count("liam@mergington.edu")
        assert count == 1


# --- DELETE /activities/{activity_name}/signup ---

class TestUnregister:
    def test_unregister_success(self):
        response = client.delete(
            "/activities/Soccer Team/signup?email=liam@mergington.edu"
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "liam@mergington.edu" in data["message"]

    def test_unregister_removes_participant(self):
        client.delete("/activities/Soccer Team/signup?email=liam@mergington.edu")
        response = client.get("/activities")
        participants = response.json()["Soccer Team"]["participants"]
        assert "liam@mergington.edu" not in participants

    def test_unregister_activity_not_found(self):
        response = client.delete(
            "/activities/Nonexistent Club/signup?email=test@mergington.edu"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Activity not found"

    def test_unregister_not_signed_up_returns_400(self):
        response = client.delete(
            "/activities/Soccer Team/signup?email=nobody@mergington.edu"
        )
        assert response.status_code == 400
        assert "not signed up" in response.json()["detail"].lower()

    def test_signup_then_unregister_roundtrip(self):
        """Full roundtrip: sign up a new student, then unregister them."""
        email = "roundtrip@mergington.edu"
        # Sign up
        resp = client.post(f"/activities/Chess Club/signup?email={email}")
        assert resp.status_code == 200
        # Verify present
        participants = client.get("/activities").json()["Chess Club"]["participants"]
        assert email in participants
        # Unregister
        resp = client.delete(f"/activities/Chess Club/signup?email={email}")
        assert resp.status_code == 200
        # Verify removed
        participants = client.get("/activities").json()["Chess Club"]["participants"]
        assert email not in participants
