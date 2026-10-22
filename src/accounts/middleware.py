"""Require a session even for unknown URLs; registration and admin stay reachable."""
from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import resolve_url
from django.urls import is_valid_path


class RequireSignInMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            match = is_valid_path(request.path_info)
            if not match and settings.APPEND_SLASH and not request.path_info.endswith("/"):
                match = is_valid_path(request.path_info + "/")
            # Use Django's public-view marker; the admin keeps its own staff gate.
            public = match and (
                not getattr(match.func, "login_required", True) or match.app_name == "admin"
            )
            if not public:
                return redirect_to_login(request.get_full_path(), resolve_url(settings.LOGIN_URL))
        return self.get_response(request)
