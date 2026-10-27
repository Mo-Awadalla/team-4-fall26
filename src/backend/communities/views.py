"""Public discovery and authenticated community management."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import NotAuthenticated, NotFound, PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Ban, Channel, Community, Invite, Membership, ModerationEvent
from .permissions import Action, require, role_for
from .serializers import (
    ChannelSerializer,
    ChannelWriteSerializer,
    CommunitySerializer,
    CommunityWriteSerializer,
    InviteWriteSerializer,
    MemberSerializer,
    RoleWriteSerializer,
)


class CommunitySessionAuthentication(SessionAuthentication):
    def authenticate_header(self, request: Request) -> str:
        return "Session"


class CommunityView(APIView):
    authentication_classes = [CommunitySessionAuthentication]


def actor(request: Request):
    if not request.user or not request.user.is_authenticated or not request.user.is_active:
        raise NotAuthenticated("Sign in with an active account to continue.")
    return request.user


def community_for(community_id: int) -> Community:
    return get_object_or_404(Community, pk=community_id)


def user_id_for(raw: str):
    """Parse the account model's primary key before applying a filter."""
    try:
        return get_user_model()._meta.pk.to_python(raw)
    except (DjangoValidationError, ValueError, TypeError) as exc:
        raise NotFound("User not found.") from exc


def summary(community: Community, user: object, role: str | None = None) -> dict:
    data = CommunitySerializer(community).data
    data["role"] = role if role is not None else role_for(community, user)
    return data


def page(request: Request) -> tuple[int, int]:
    class Page(serializers.Serializer):
        limit = serializers.IntegerField(default=20, min_value=1, max_value=50)
        offset = serializers.IntegerField(default=0, min_value=0)

    parsed = Page(data=request.query_params)
    parsed.is_valid(raise_exception=True)
    return parsed.validated_data["limit"], parsed.validated_data["offset"]


class CommunityList(CommunityView):
    def get(self, request: Request) -> Response:
        limit, offset = page(request)
        query = request.query_params.get("q", "").strip()[:100]
        communities = Community.objects.annotate(member_count=Count("memberships"))
        if query:
            communities = communities.filter(
                Q(name__icontains=query) | Q(school__icontains=query) | Q(course__icontains=query)
            )
        if request.query_params.get("mine") == "true":
            user = actor(request)
            communities = communities.filter(memberships__user=user)
        found = list(communities[offset : offset + limit + 1])
        roles = {}
        if request.user and request.user.is_authenticated:
            roles = dict(
                Membership.objects.filter(
                    user=request.user, community__in=found[:limit]
                ).values_list("community_id", "role")
            )
        return Response(
            {
                "items": [
                    summary(
                        item,
                        request.user,
                        "owner"
                        if item.owner_id == getattr(request.user, "pk", None)
                        else roles.get(item.pk, "visitor"),
                    )
                    for item in found[:limit]
                ],
                "has_more": len(found) > limit,
            }
        )

    def post(self, request: Request) -> Response:
        user = actor(request)
        parsed = CommunityWriteSerializer(data=request.data)
        parsed.is_valid(raise_exception=True)
        created = services.create_community(user, parsed.validated_data)
        created.member_count = 1
        return Response(summary(created, user), status=201)


class CommunityDetail(CommunityView):
    def get(self, request: Request, community_id: int) -> Response:
        community = get_object_or_404(
            Community.objects.annotate(member_count=Count("memberships")), pk=community_id
        )
        return Response(
            {
                **summary(community, request.user),
                "channels": ChannelSerializer(community.channels.all(), many=True).data,
            }
        )

    def patch(self, request: Request, community_id: int) -> Response:
        user = actor(request)
        parsed = CommunityWriteSerializer(data=request.data, partial=True)
        parsed.is_valid(raise_exception=True)
        with transaction.atomic():
            community = get_object_or_404(Community.objects.select_for_update(), pk=community_id)
            require(community, user, Action.MANAGE)
            for field, value in parsed.validated_data.items():
                setattr(community, field, value)
            if parsed.validated_data:
                community.save(update_fields=list(parsed.validated_data))
        community.member_count = community.memberships.count()
        return Response(summary(community, user))

    def delete(self, request: Request, community_id: int) -> Response:
        user = actor(request)
        with transaction.atomic():
            community = get_object_or_404(Community.objects.select_for_update(), pk=community_id)
            require(community, user, Action.DELETE)
            community.delete()
        return Response(status=204)


class Join(CommunityView):
    def post(self, request: Request, community_id: int) -> Response:
        services.join(community_for(community_id), actor(request))
        return Response({"joined": True})


class Leave(CommunityView):
    def post(self, request: Request, community_id: int) -> Response:
        services.leave(community_for(community_id), actor(request))
        return Response({"joined": False})


class Members(CommunityView):
    def get(self, request: Request, community_id: int) -> Response:
        community = community_for(community_id)
        limit, offset = page(request)
        found = list(
            Membership.objects.filter(community=community).order_by("id")[
                offset : offset + limit + 1
            ]
        )
        return Response(
            {
                "items": MemberSerializer(found[:limit], many=True).data,
                "has_more": len(found) > limit,
            }
        )


class MemberDetail(CommunityView):
    def patch(self, request: Request, community_id: int, user_id: str) -> Response:
        parsed = RoleWriteSerializer(data=request.data)
        parsed.is_valid(raise_exception=True)
        services.set_role(
            community_for(community_id),
            actor(request),
            user_id_for(user_id),
            parsed.validated_data["role"],
        )
        return Response({"role": parsed.validated_data["role"]})

    def delete(self, request: Request, community_id: int, user_id: str) -> Response:
        services.moderate(community_for(community_id), actor(request), user_id_for(user_id), "kick")
        return Response(status=204)


class Transfer(CommunityView):
    def post(self, request: Request, community_id: int) -> Response:
        class Target(serializers.Serializer):
            user_id = serializers.CharField(max_length=64)

        parsed = Target(data=request.data)
        parsed.is_valid(raise_exception=True)
        services.transfer(
            community_for(community_id),
            actor(request),
            user_id_for(parsed.validated_data["user_id"]),
        )
        return Response({"owner_id": parsed.validated_data["user_id"]})


class Channels(CommunityView):
    def get(self, request: Request, community_id: int) -> Response:
        community = community_for(community_id)
        return Response(ChannelSerializer(community.channels.all(), many=True).data)

    def post(self, request: Request, community_id: int) -> Response:
        parsed = ChannelWriteSerializer(data=request.data)
        parsed.is_valid(raise_exception=True)
        channel = services.create_channel(
            community_for(community_id), actor(request), parsed.validated_data["name"]
        )
        return Response(ChannelSerializer(channel).data, status=201)


class ChannelDetail(CommunityView):
    def patch(self, request: Request, community_id: int, channel_id: int) -> Response:
        user = actor(request)

        class Update(serializers.Serializer):
            name = serializers.RegexField(r"^[a-z0-9][a-z0-9-]{0,49}$", required=False)
            position = serializers.IntegerField(min_value=0, max_value=19, required=False)
            archived = serializers.BooleanField(required=False)

        parsed = Update(data=request.data)
        parsed.is_valid(raise_exception=True)
        with transaction.atomic():
            community = get_object_or_404(Community.objects.select_for_update(), pk=community_id)
            require(community, user, Action.MANAGE)
            channel = get_object_or_404(Channel, pk=channel_id, community=community)
            name = parsed.validated_data.get("name")
            if (
                name
                and Channel.objects.filter(community=community, name__iexact=name)
                .exclude(pk=channel.pk)
                .exists()
            ):
                raise serializers.ValidationError("A channel with this name already exists.")
            position = parsed.validated_data.pop("position", None)
            if position is not None:
                ordered = list(
                    Channel.objects.filter(community=community).order_by("position", "id")
                )
                ordered.remove(channel)
                ordered.insert(min(position, len(ordered)), channel)
                for index, item in enumerate(ordered):
                    item.position = index
                Channel.objects.bulk_update(ordered, ["position"])
            for field, value in parsed.validated_data.items():
                setattr(channel, field, value)
            if parsed.validated_data:
                channel.save(update_fields=list(parsed.validated_data))
        return Response(ChannelSerializer(channel).data)


class Invites(CommunityView):
    def get(self, request: Request, community_id: int) -> Response:
        community = community_for(community_id)
        require(community, actor(request), Action.INVITE)
        return Response(
            list(
                Invite.objects.filter(community=community)
                .values("id", "created_at", "expires_at", "max_uses", "uses", "revoked")
                .order_by("-id")[:50]
            )
        )

    def post(self, request: Request, community_id: int) -> Response:
        parsed = InviteWriteSerializer(data=request.data)
        parsed.is_valid(raise_exception=True)
        invite, token = services.create_invite(
            community_for(community_id), actor(request), parsed.validated_data
        )
        return Response(
            {
                "id": invite.id,
                "token": token,
                "expires_at": invite.expires_at,
                "max_uses": invite.max_uses,
            },
            status=201,
        )


class InviteDetail(CommunityView):
    def delete(self, request: Request, community_id: int, invite_id: int) -> Response:
        with transaction.atomic():
            community = get_object_or_404(Community.objects.select_for_update(), pk=community_id)
            require(community, actor(request), Action.INVITE)
            invite = get_object_or_404(Invite, pk=invite_id, community=community)
            invite.revoked = True
            invite.save(update_fields=["revoked"])
        return Response(status=204)


class Redeem(CommunityView):
    def post(self, request: Request, token: str) -> Response:
        community = services.redeem(token, actor(request))
        return Response({"community_id": community.pk})


class Moderation(CommunityView):
    def get(self, request: Request, community_id: int) -> Response:
        community = community_for(community_id)
        require(community, actor(request), Action.MODERATE)
        return Response(
            {
                "events": list(
                    ModerationEvent.objects.filter(community=community).values(
                        "id", "actor_id", "target_id", "action", "created_at"
                    )[:50]
                ),
                "banned_user_ids": list(
                    Ban.objects.filter(community=community).values_list("user_id", flat=True)[:50]
                ),
            }
        )

    def post(self, request: Request, community_id: int) -> Response:
        class Decision(serializers.Serializer):
            user_id = serializers.CharField(max_length=64)
            action = serializers.ChoiceField(choices=["ban", "unban", "kick"])

        parsed = Decision(data=request.data)
        parsed.is_valid(raise_exception=True)
        target_id = user_id_for(parsed.validated_data["user_id"])
        if not get_user_model().objects.filter(pk=target_id).exists():
            raise NotFound("User not found.")
        services.moderate(
            community_for(community_id), actor(request), target_id, parsed.validated_data["action"]
        )
        return Response({"action": parsed.validated_data["action"]})


class AdminCommunity(CommunityView):
    """A separate platform action, never an implicit community owner grant."""

    def delete(self, request: Request, community_id: int) -> Response:
        user = actor(request)
        if not user.is_staff:
            raise PermissionDenied("A StudySpot admin account is required.")
        with transaction.atomic():
            community = get_object_or_404(Community.objects.select_for_update(), pk=community_id)
            community.delete()
        return Response(status=204)
