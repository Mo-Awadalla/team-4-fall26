"""Account routes, without trailing slashes like every other route."""

from django.urls import path

from .views import AccountView, AuthConfigView

urlpatterns = [
    path("auth/config", AuthConfigView.as_view(), name="auth-config"),
    path("account", AccountView.as_view(), name="account"),
]
