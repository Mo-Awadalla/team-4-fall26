"""Interactions shared by channel members and direct conversation participants."""

from datetime import timedelta

from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from .dm_views import conversation_for, person_key
from .message_views import author_name, channel_for, member_role, poll_data
from .models import DirectMessage, RoomMemberState, Vote
from .views import CommunityView


def room_messages(request, *, community_id=None, channel_id=None, conversation_id=None):
    if conversation_id is not None:
        conversation, key = conversation_for(request, conversation_id)
        return DirectMessage.objects.filter(conversation=conversation), key
    channel = channel_for(community_id, channel_id)
    member_role(request, channel)
    return channel.messages.all(), person_key(request)


class PollVote(CommunityView):
    def put(self, request, message_id, **room):
        messages, key = room_messages(request, **room)
        message = get_object_or_404(messages, pk=message_id, deleted_at__isnull=True)
        if not message.poll_id:
            raise NotFound("Poll unavailable.")
        class Ballot(serializers.Serializer):
            choice = serializers.IntegerField(min_value=0, max_value=len(message.poll.options)-1)
        parsed = Ballot(data=request.data)
        parsed.is_valid(raise_exception=True)
        Vote.objects.update_or_create(poll=message.poll, actor=key, defaults=parsed.validated_data)
        return Response(poll_data(messages.get(pk=message_id), key))


def room_state(room):
    if "conversation_id" in room:
        return RoomMemberState.objects.filter(conversation_id=room["conversation_id"])
    return RoomMemberState.objects.filter(channel_id=room["channel_id"])


class RoomPresence(CommunityView):
    def get(self, request, **room):
        _, key = room_messages(request, **room)
        names = room_state(room).exclude(actor=key).filter(typing_until__gt=timezone.now()).order_by("-typing_until").values_list("name", flat=True)[:5]
        return Response({"typing": list(names)})

    def post(self, request, **room):
        _, key = room_messages(request, **room)
        class Signal(serializers.Serializer):
            typing = serializers.BooleanField(required=False)
        parsed = Signal(data=request.data)
        parsed.is_valid(raise_exception=True)
        defaults = {"name": author_name(request), "last_active": timezone.now()}
        if "typing" in parsed.validated_data:
            defaults["typing_until"] = timezone.now() + timedelta(seconds=7) if parsed.validated_data["typing"] else None
        scope = {k:v for k,v in room.items() if k != "community_id"}
        RoomMemberState.objects.update_or_create(actor=key, **scope, defaults=defaults)
        return Response(status=204)
