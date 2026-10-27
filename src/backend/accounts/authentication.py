"""Authenticating requests with an Auth0 access token.

The browser logs in with Auth0 and sends the access token it receives as
``Authorization: Bearer <token>``. Verifying it needs nothing from Auth0 at
request time but its public signing keys, which is what lets the deployed API
check tokens with no route to the internet: Terraform reads the keys once at
apply time and passes them in as ``AUTH0_JWKS``.

A request with no token is anonymous rather than rejected, so that one class can
sit in front of public and private routes alike. A request with a token that
does not verify is rejected outright: a client that sent one meant to be
somebody, and quietly treating it as nobody would hide the problem.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from typing import Any

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from .models import Account

#: Auth0 signs access tokens for a custom API with RS256 unless told otherwise.
#: Naming the one algorithm accepted is what stops a token from choosing its own.
ALGORITHMS = ["RS256"]

#: Tolerated clock difference between Auth0 and the Lambda host, in seconds.
LEEWAY = 30


@dataclass(frozen=True)
class Identity:
    """What a verified token says about who sent it."""

    subject: str
    email: str
    email_verified: bool
    username: str


def configured() -> bool:
    """Whether accounts are switched on in this environment."""
    return bool(settings.AUTH0_DOMAIN and settings.AUTH0_CLIENT_ID and settings.AUTH0_AUDIENCE)


def issuer() -> str:
    # Auth0's issuer is the tenant URL with a trailing slash, and the comparison
    # is exact.
    return f"https://{settings.AUTH0_DOMAIN}/"


@cache
def _key_set(document: str) -> jwt.PyJWKSet:
    """Parse a JWKS document once per distinct value."""
    return jwt.PyJWKSet.from_dict(json.loads(document))


@cache
def _key_client(domain: str) -> jwt.PyJWKClient:
    """Fetch keys from the tenant, for development, which has a network."""
    return jwt.PyJWKClient(f"https://{domain}/.well-known/jwks.json", cache_keys=True)


def signing_key(token: str) -> Any:
    """The public key that should have signed ``token``, chosen by its ``kid``."""
    if settings.AUTH0_JWKS:
        kid = jwt.get_unverified_header(token).get("kid")
        for key in _key_set(settings.AUTH0_JWKS).keys:
            if key.key_id == kid:
                return key.key
        raise jwt.InvalidTokenError("The token was signed by a key this API does not know.")
    return _key_client(settings.AUTH0_DOMAIN).get_signing_key_from_jwt(token).key


def verify(token: str) -> Identity:
    """Check ``token`` and read the identity out of it.

    Raises :class:`jwt.InvalidTokenError` (or a subclass) for anything wrong
    with it, and :class:`jwt.PyJWKClientError` when the keys cannot be fetched.
    """
    claims = jwt.decode(
        token,
        signing_key(token),
        algorithms=ALGORITHMS,
        audience=settings.AUTH0_AUDIENCE,
        issuer=issuer(),
        leeway=LEEWAY,
        options={"require": ["exp", "iat", "sub"]},
    )

    # Auth0 leaves the email out of an access token. The post-login Action in
    # docs/source/accounts.md adds it, with the verification flag and the
    # username, under a namespace.
    namespace = settings.AUTH0_CLAIM_NAMESPACE
    return Identity(
        subject=claims["sub"],
        email=str(claims.get(f"{namespace}email") or "").strip().lower(),
        email_verified=claims.get(f"{namespace}email_verified") is True,
        username=str(claims.get(f"{namespace}username") or "").strip(),
    )


def account_for(identity: Identity) -> Account:
    """Find or create the account ``identity`` belongs to, refreshed from it."""
    with transaction.atomic():
        user, _ = get_user_model().objects.get_or_create(username=identity.subject)
        account, created = Account.objects.select_for_update().get_or_create(
            user=user,
            defaults={
                "email": identity.email,
                "email_verified": identity.email_verified,
                "username": identity.username,
            },
        )

        if not created:
            current = {
                "email": identity.email,
                "email_verified": identity.email_verified,
                "username": identity.username,
            }
            changed = [name for name, value in current.items() if getattr(account, name) != value]
            if changed:
                for name in changed:
                    setattr(account, name, current[name])
                account.save(update_fields=[*changed, "updated_at"])

    return account


class Auth0Authentication(BaseAuthentication):
    """DRF authentication from an Auth0 bearer token."""

    keyword = b"bearer"

    def authenticate(self, request: Request) -> tuple[Any, Identity] | None:
        header = get_authorization_header(request).split()
        if not header or header[0].lower() != self.keyword:
            return None

        if len(header) != 2:
            raise AuthenticationFailed("The Authorization header must be 'Bearer <token>'.")

        if not configured():
            raise AuthenticationFailed("Accounts are not configured on this server.")

        try:
            identity = verify(header[1].decode("ascii"))
        except (UnicodeDecodeError, jwt.InvalidTokenError) as error:
            raise AuthenticationFailed("The access token is not valid.") from error
        except jwt.PyJWKClientError as error:
            raise AuthenticationFailed("The signing keys could not be loaded.") from error

        return account_for(identity).user, identity

    def authenticate_header(self, request: Request) -> str:
        # Present, so DRF answers a missing or bad token with 401 rather than 403.
        return 'Bearer realm="api"'
