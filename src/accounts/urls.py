from django.urls import include, path

from accounts import recovery, views


registration_patterns = [
    path("signup/", views.signup, name="signup"),
    path("check-email/", views.check_email, name="check_email"),
    path("verify/<str:token>/", views.verify, name="verify"),
    path("created/", views.created, name="created"),
    path("forgot-password/", recovery.forgot_password, name="forgot_password"),
    path("reset-sent/", recovery.reset_sent, name="reset_sent"),
    path("reset/<str:uidb64>/<str:token>/", recovery.ResetPasswordView.as_view(), name="reset_password"),
    path("reset-complete/", recovery.reset_complete, name="reset_complete"),
]

urlpatterns = [
    path("sign-in/", views.sign_in, name="sign_in"),
    path("sign-out/", views.sign_out, name="sign_out"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("accounts/", include((registration_patterns, "accounts"))),
]
