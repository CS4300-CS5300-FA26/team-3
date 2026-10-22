from django.urls import include, path

from accounts import views


registration_patterns = [
    path("signup/", views.signup, name="signup"),
    path("check-email/", views.check_email, name="check_email"),
    path("verify/<str:token>/", views.verify, name="verify"),
    path("created/", views.created, name="created"),
]

urlpatterns = [
    path("sign-in/", views.sign_in, name="sign_in"),
    path("sign-out/", views.sign_out, name="sign_out"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("accounts/", include((registration_patterns, "accounts"))),
]
