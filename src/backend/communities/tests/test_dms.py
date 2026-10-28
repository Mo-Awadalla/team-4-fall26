"""Private conversations are visible only to their two participants."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_two_guests_can_start_and_exchange_private_messages():
    first = APIClient()
    community_id = first.post("/communities", {"name": "Calculus"}).data["id"]
    channel_id = first.get(f"/communities/{community_id}").data["channels"][0]["id"]
    second = APIClient()
    assert second.post(f"/communities/{community_id}/join").status_code == 200
    channel_path = f"/communities/{community_id}/channels/{channel_id}/messages"
    public_message_id = second.post(channel_path, {"content": "Can we study?"}).data["id"]
    started = first.post(f"{channel_path}/{public_message_id}/dm")
    assert started.status_code == 201
    dm_id = started.data["id"]
    assert second.get("/dms").data["items"][0]["id"] == dm_id
    assert first.post(f"{channel_path}/{public_message_id}/dm").data["id"] == dm_id
    third = APIClient()
    assert third.get(f"/dms/{dm_id}/messages").status_code == 403
    assert third.post(f"/communities/{community_id}/join").status_code == 200
    assert third.get(f"/dms/{dm_id}/messages").status_code == 404

    messages = f"/dms/{dm_id}/messages"
    sent = first.post(messages, {"content": "Sure, Friday at 2."})
    assert sent.status_code == 201
    message_id = sent.data["id"]
    assert second.get(messages).data["items"][0]["content"] == "Sure, Friday at 2."
    assert second.patch(f"{messages}/{message_id}", {"content": "No"}).status_code == 403
    assert first.patch(f"{messages}/{message_id}", {"content": "Friday at 3."}).status_code == 200
    assert second.post(messages, {"content": "Works!", "reply_to": message_id}).status_code == 201
    assert first.delete(f"{messages}/{message_id}").status_code == 204
    assert second.get(messages).data["items"][0]["deleted_at"] is not None


def test_guest_can_start_dm_with_account_member():
    owner = APIClient()
    community_id = owner.post("/communities", {"name": "Physics"}).data["id"]
    user = get_user_model().objects.create_user(username="student", password="test-password")
    account = APIClient()
    account.force_authenticate(user=user)
    assert account.post(f"/communities/{community_id}/join").status_code == 200
    started = owner.post(f"/communities/{community_id}/dms", {"user_id": str(user.pk)})
    assert started.status_code == 201
    assert account.get("/dms").data["items"][0]["id"] == started.data["id"]
    assert account.post(f"/dms/{started.data['id']}/messages", {"content": "Hi"}).status_code == 201
