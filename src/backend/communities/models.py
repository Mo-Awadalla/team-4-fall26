"""Public communities and their membership boundaries."""

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


class Community(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(max_length=1000, blank=True)
    school = models.CharField(max_length=100, blank=True)
    course = models.CharField(max_length=100, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.name}"


class Membership(models.Model):
    class Role(models.TextChoices):
        MEMBER = "member"
        MODERATOR = "moderator"

    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["community", "user"], name="member_once")]
        indexes = [models.Index(fields=["user", "community"], name="member_user_community")]

    def __str__(self) -> str:
        return f"{self.user_id} in {self.community_id}"


class GuestMembership(models.Model):
    community = models.ForeignKey(
        Community, on_delete=models.CASCADE, related_name="guest_memberships"
    )
    guest_id = models.CharField(max_length=32)
    joined_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["community", "guest_id"], name="guest_member_once")
        ]
        indexes = [models.Index(fields=["expires_at"], name="guest_membership_expiry")]

    def __str__(self) -> str:
        return f"Guest in {self.community_id}"


class Channel(models.Model):
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="channels")
    name = models.CharField(max_length=50)
    position = models.PositiveSmallIntegerField(default=0)
    archived = models.BooleanField(default=False)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(Lower("name"), "community", name="channel_name_per_community")
        ]

    def __str__(self) -> str:
        return f"{self.name}"


class Ban(models.Model):
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="bans")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["community", "user"], name="ban_once")]

    def __str__(self) -> str:
        return f"{self.user_id} banned from {self.community_id}"


class Invite(models.Model):
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="invites")
    token_hash = models.CharField(max_length=64, unique=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    uses = models.PositiveIntegerField(default=0)
    revoked = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"Invite {self.pk} for {self.community_id}"


class ModerationEvent(models.Model):
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="moderation")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    target = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    action = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self) -> str:
        return f"{self.action} in {self.community_id}"
