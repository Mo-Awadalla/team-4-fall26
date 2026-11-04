"""Interactions shared by channel members and direct conversation participants."""

from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from .dm_views import conversation_for, person_key
from .message_views import channel_for, member_role, poll_data
from .models import DirectMessage, Vote
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
