"""Public discovery and session-backed community management."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import NotAuthenticated, NotFound, PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import Auth0Authentication

from . import services
from .models import Ban, Channel, Community, Invite, Membership, ModerationEvent
from .permissions import Action, GuestOwner, require, role_for
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
    def authenticate(self, request: Request):
        if request.method not in {"GET", "HEAD", "OPTIONS"} and not getattr(
            request._request.user, "is_authenticated", False
        ):
            self.enforce_csrf(request)
        return super().authenticate(request)

    def authenticate_header(self, request: Request) -> str:
        return "Session"


class CommunityView(APIView):
    authentication_classes = [Auth0Authentication, CommunitySessionAuthentication]


def actor(request: Request):
    if not request.user or not request.user.is_authenticated or not request.user.is_active:
        raise NotAuthenticated("Sign in with an active account to continue.")
    return request.user


def viewer(request: Request, community: Community):
    if community.owner_id is None and community.pk in request.session.get("guest_communities", []):
        return GuestOwner(community.pk)
    return request.user


def principal(request: Request, community: Community):
    user = viewer(request, community)
    return user if isinstance(user, GuestOwner) else actor(request)


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
        get_token(request._request)
        limit, offset = page(request)
        query = request.query_params.get("q", "").strip()
        if len(query) > 100:
            raise serializers.ValidationError({"q": "Search must be at most 100 characters."})
        mine = request.query_params.get("mine")
        if mine not in {None, "true", "false"}:
            raise serializers.ValidationError({"mine": "Use true or false."})
        communities = Community.objects.annotate(member_count=Count("memberships"))
        if query:
            communities = communities.filter(
                Q(name__icontains=query) | Q(school__icontains=query) | Q(course__icontains=query)
            )
        guest_ids = request.session.get("guest_communities", [])
        if mine == "true":
            if getattr(request.user, "is_authenticated", False):
                communities = communities.filter(
                    Q(memberships__user=request.user) | Q(pk__in=guest_ids, owner__isnull=True)
                )
            else:
                communities = communities.filter(pk__in=guest_ids, owner__isnull=True)
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
                        if (
                            item.owner_id is not None
                            and item.owner_id == getattr(request.user, "pk", None)
                        )
                        or (item.owner_id is None and item.pk in guest_ids)
                        else roles.get(item.pk, "visitor"),
                    )
                    for item in found[:limit]
                ],
                "has_more": len(found) > limit,
            }
        )

    def post(self, request: Request) -> Response:
        parsed = CommunityWriteSerializer(data=request.data)
        parsed.is_valid(raise_exception=True)
        if getattr(request.user, "is_authenticated", False):
            created = services.create_community(actor(request), parsed.validated_data)
            created.member_count = 1
        else:
            owned = list(
                Community.objects.filter(
                    pk__in=request.session.get("guest_communities", []), owner__isnull=True
                ).values_list("pk", flat=True)
            )
            if len(owned) >= services.MAX_OWNED:
                raise serializers.ValidationError("You own the maximum number of communities.")
            created = services.create_guest_community(parsed.validated_data)
            request.session["guest_communities"] = [*owned, created.pk]
            created.member_count = 0
        return Response(summary(created, viewer(request, created)), status=201)


class CommunityDetail(CommunityView):
    def get(self, request: Request, community_id: int) -> Response:
        community = get_object_or_404(
            Community.objects.annotate(member_count=Count("memberships")), pk=community_id
        )
        return Response(
            {
                **summary(community, viewer(request, community)),
                "channels": ChannelSerializer(community.channels.all(), many=True).data,
            }
        )

    def patch(self, request: Request, community_id: int) -> Response:
        parsed = CommunityWriteSerializer(data=request.data, partial=True)
        parsed.is_valid(raise_exception=True)
        with transaction.atomic():
            community = get_object_or_404(Community.objects.select_for_update(), pk=community_id)
            user = principal(request, community)
            require(community, user, Action.MANAGE)
            for field, value in parsed.validated_data.items():
                setattr(community, field, value)
            if parsed.validated_data:
                community.save(update_fields=list(parsed.validated_data))
        community.member_count = community.memberships.count()
        return Response(summary(community, user))

    def delete(self, request: Request, community_id: int) -> Response:
        with transaction.atomic():
            community = get_object_or_404(Community.objects.select_for_update(), pk=community_id)
            user = principal(request, community)
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
        community = community_for(community_id)
        services.set_role(
            community,
            principal(request, community),
            user_id_for(user_id),
            parsed.validated_data["role"],
        )
        return Response({"role": parsed.validated_data["role"]})

    def delete(self, request: Request, community_id: int, user_id: str) -> Response:
        community = community_for(community_id)
        services.moderate(community, principal(request, community), user_id_for(user_id), "kick")
        return Response(status=204)


class Transfer(CommunityView):
    def post(self, request: Request, community_id: int) -> Response:
        class Target(serializers.Serializer):
            user_id = serializers.CharField(max_length=64)

        parsed = Target(data=request.data)
        parsed.is_valid(raise_exception=True)
        community = community_for(community_id)
        services.transfer(
            community,
            principal(request, community),
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
        community = community_for(community_id)
        channel = services.create_channel(
            community, principal(request, community), parsed.validated_data["name"]
        )
        return Response(ChannelSerializer(channel).data, status=201)


class ChannelDetail(CommunityView):
    def patch(self, request: Request, community_id: int, channel_id: int) -> Response:
        class Update(serializers.Serializer):
            name = serializers.RegexField(r"^[a-z0-9][a-z0-9-]{0,49}$", required=False)
            position = serializers.IntegerField(min_value=0, max_value=19, required=False)
            archived = serializers.BooleanField(required=False)

        parsed = Update(data=request.data)
        parsed.is_valid(raise_exception=True)
        with transaction.atomic():
            community = get_object_or_404(Community.objects.select_for_update(), pk=community_id)
            user = principal(request, community)
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
        require(community, principal(request, community), Action.INVITE)
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
        community = community_for(community_id)
        invite, token = services.create_invite(
            community, principal(request, community), parsed.validated_data
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
            require(community, principal(request, community), Action.INVITE)
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
        require(community, principal(request, community), Action.MODERATE)
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
        community = community_for(community_id)
        services.moderate(
            community, principal(request, community), target_id, parsed.validated_data["action"]
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
