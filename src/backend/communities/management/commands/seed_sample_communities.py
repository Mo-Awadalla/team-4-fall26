"""Create repeatable local-only sample communities and conversations."""

import hashlib

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Account, AccountType
from communities.models import (
    Channel,
    Community,
    DirectConversation,
    DirectMessage,
    GuestMembership,
    Membership,
    Message,
)

PEOPLE = {"maya": "Maya", "jordan": "Jordan", "sam": "Sam"}
GROUPS = (
    (
        "NYU Calculus Study Circle",
        "Problem sets, office hours, and exam prep for calculus.",
        "New York University",
        "MATH 51A",
        "maya",
        {
            "general": ("maya", "Welcome! Share the problem set you are working on."),
            "exam-prep": ("jordan", "I made a review outline for Friday's study session."),
        },
    ),
    (
        "Queens Biology Lab",
        "Compare lab notes and plan study sessions together.",
        "CUNY Queens College",
        "BIO 101",
        "jordan",
        {
            "general": ("jordan", "Our next lab review is Tuesday afternoon."),
            "lab-notes": ("sam", "Bring your microscopy notes to the session."),
        },
    ),
    (
        "MIT Algorithms Club",
        "Work through algorithms and practice problems as a group.",
        "Massachusetts Institute of Technology",
        "6.006",
        "sam",
        {
            "general": ("sam", "Post a topic you want to cover this week."),
            "practice": ("maya", "Let's start with graph traversal examples."),
        },
    ),
)


class Command(BaseCommand):
    help = "Seed local sample communities; optionally add DMs to one guest-owned community."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--guest-community", type=int)

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        if not settings.DEBUG:
            raise CommandError("Sample data can only be seeded with DJANGO_DEBUG=true.")

        users = {}
        for handle, display_name in PEOPLE.items():
            user, created = get_user_model().objects.get_or_create(
                username=f"studyspot_sample_{handle}"
            )
            if created:
                user.set_unusable_password()
                user.save(update_fields=["password"])
            Account.objects.get_or_create(
                user=user,
                defaults={"username": display_name, "account_type": AccountType.STUDENT},
            )
            users[handle] = user

        for name, description, school, course, owner, posts in GROUPS:
            community, _ = Community.objects.get_or_create(
                name=name,
                owner=users[owner],
                defaults={"description": description, "school": school, "course": course},
            )
            for user in users.values():
                Membership.objects.get_or_create(community=community, user=user)
            for position, (channel_name, (author, content)) in enumerate(posts.items()):
                channel, _ = Channel.objects.get_or_create(
                    community=community, name=channel_name, defaults={"position": position}
                )
                Message.objects.get_or_create(
                    channel=channel,
                    author=users[author],
                    content=content,
                    defaults={"author_name": PEOPLE[author]},
                )

        guest_community_id = options["guest_community"]
        if guest_community_id is not None:
            community = Community.objects.filter(pk=guest_community_id, owner__isnull=True).first()
            if community is None:
                raise CommandError("Choose an existing guest-owned community.")
            guests = list(
                GuestMembership.objects.filter(
                    community=community, expires_at__gt=timezone.now()
                ).values_list("guest_id", flat=True)
            )
            if len(guests) != 1:
                raise CommandError("The guest-owned community must have exactly one active guest.")
            guest_key = f"g:{guests[0]}"
            channel = community.channels.order_by("position", "id").first()
            if channel is None:
                raise CommandError("The guest-owned community has no channel.")
            for handle, content, dm_text in (
                (
                    "maya",
                    "I can help review the first practice set.",
                    "Want to plan a study session?",
                ),
                (
                    "jordan",
                    "I am working through the exam outline.",
                    "I shared an exam outline in the channel.",
                ),
            ):
                user = users[handle]
                Membership.objects.get_or_create(community=community, user=user)
                Message.objects.get_or_create(
                    channel=channel,
                    author=user,
                    content=content,
                    defaults={"author_name": PEOPLE[handle]},
                )
                account_key = f"u:{user.pk}"
                first, second = sorted((account_key, guest_key))
                conversation, _ = DirectConversation.objects.get_or_create(
                    pair_key=hashlib.sha256(f"{first}\0{second}".encode()).hexdigest(),
                    defaults={
                        "first_key": first,
                        "second_key": second,
                        "first_name": PEOPLE[handle] if first == account_key else "You",
                        "second_name": PEOPLE[handle] if second == account_key else "You",
                    },
                )
                DirectMessage.objects.get_or_create(
                    conversation=conversation,
                    sender_key=account_key,
                    content=dm_text,
                    defaults={"author_name": PEOPLE[handle]},
                )

        self.stdout.write(self.style.SUCCESS("Sample communities and conversations are ready."))
