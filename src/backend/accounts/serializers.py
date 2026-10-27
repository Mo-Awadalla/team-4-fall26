"""Shapes of the account routes' requests and responses."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from rest_framework import serializers

from .models import Account, AccountType


class AccountSerializer(serializers.ModelSerializer):
    """An account as its owner sees it.

    ``account_type`` is ``null`` until sign-up is finished, which is how the
    frontend knows to ask.
    """

    account_type = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = (
            "email",
            "email_verified",
            "username",
            "account_type",
            "business_name",
            "created_at",
        )
        read_only_fields = fields

    def get_account_type(self, account: Account) -> str | None:
        return str(account.account_type) or None


def is_student_email(email: str) -> bool:
    """Whether ``email`` is at one of the domains a student account allows."""
    _, _, domain = email.rpartition("@")
    domain = domain.lower()
    return any(
        domain == allowed or domain.endswith(f".{allowed}")
        for allowed in settings.STUDENT_EMAIL_DOMAINS
    )


class CompleteSignUpSerializer(serializers.Serializer):
    """The one decision Auth0's sign-up form does not make: which kind of account.

    Validated against the account it will be applied to, because what is
    allowed depends on the email Auth0 verified, not on anything in the body.
    """

    account_type = serializers.ChoiceField(choices=AccountType.choices)
    business_name = serializers.CharField(
        max_length=200, required=False, allow_blank=True, trim_whitespace=True
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        account: Account = self.context["account"]
        account_type = attrs["account_type"]
        business_name = attrs.get("business_name", "")

        if not account.email_verified:
            raise serializers.ValidationError(
                {"email": "Verify your email address before finishing sign-up."},
                code="email_unverified",
            )

        if account_type == AccountType.STUDENT:
            if not is_student_email(str(account.email)):
                raise serializers.ValidationError(
                    {"email": "A student account needs a university email address."},
                    code="not_a_student_email",
                )
            if not account.username:
                raise serializers.ValidationError(
                    {"username": "A student account needs a username."},
                    code="required",
                )
            if business_name:
                raise serializers.ValidationError(
                    {"business_name": "Only a business account has a business name."},
                    code="not_allowed",
                )

        if account_type == AccountType.BUSINESS and not business_name:
            raise serializers.ValidationError(
                {"business_name": "A business account needs a business name."},
                code="required",
            )

        return {"account_type": account_type, "business_name": business_name}
