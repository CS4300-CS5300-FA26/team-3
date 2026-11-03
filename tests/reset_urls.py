"""Isolated route stand-in for service tests; public flow tests use real routes."""
from django.http import HttpResponse
from django.urls import include, path


def completion(request, uidb64, token):
    return HttpResponse()


urlpatterns = [path("accounts/", include(([
    path("reset/<uidb64>/<token>/", completion, name="reset_password"),
], "accounts")))]
