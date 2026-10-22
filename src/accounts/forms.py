from django import forms

from accounts.identity import normalize_email


class SignupForm(forms.Form):
    email = forms.CharField(
        label="Email", strip=False,
        widget=forms.EmailInput(attrs={"autocomplete": "email", "maxlength": 150}),
    )

    def clean_email(self):
        return normalize_email(self.cleaned_data["email"])


class SetPasswordForm(forms.Form):
    password = forms.CharField(
        label="Password", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Use at least 8 characters.",
    )
    password_confirmation = forms.CharField(
        label="Confirm password", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
