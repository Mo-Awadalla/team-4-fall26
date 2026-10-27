"""Account routes.

``GET /auth/config`` is public: it tells the browser which Auth0 tenant to log
in with, so that the frontend build carries no environment of its own.
``/account`` needs a valid access token.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import Auth0Authentication, configured
from .models import Account
from .serializers import AccountSerializer, CompleteSignUpSerializer


class SignUpAlreadyComplete(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This account has already finished signing up."
    default_code = "conflict"


class AuthConfigView(APIView):
    """The public Auth0 settings the browser needs to start a log-in."""

    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    def get(self, request: Request) -> Response:
        if not configured():
            return Response({"enabled": False})
        return Response(
            {
                "enabled": True,
                "domain": settings.AUTH0_DOMAIN,
                "client_id": settings.AUTH0_CLIENT_ID,
                "audience": settings.AUTH0_AUDIENCE,
            }
        )


class AccountView(APIView):
    """The logged-in person's own account.

    ``GET`` creates it on the first request after an Auth0 sign-up, so there is
    no separate registration call to forget. ``POST`` finishes sign-up by
    choosing student or business, once.
    """

    authentication_classes = [Auth0Authentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(AccountSerializer(self._account(request)).data)

    def post(self, request: Request) -> Response:
        account = self._account(request)
        if account.account_type:
            raise SignUpAlreadyComplete()

        serializer = CompleteSignUpSerializer(data=request.data, context={"account": account})
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data

        account.account_type = data["account_type"]
        account.business_name = data["business_name"]
        account.save(update_fields=["account_type", "business_name", "updated_at"])
        return Response(AccountSerializer(account).data, status=status.HTTP_201_CREATED)

    @staticmethod
    def _account(request: Request) -> Account:
        return request.user.account
