
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.validators import RegexValidator

from .models import Ticket, TicketComment, UserProfile


# -----------------------------
# Ticket Creation Form
# -----------------------------
class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = [
            "title",
            "description",
            "user_name",
            "category",
            "priority",
        ]

        widgets = {
            "title": forms.TextInput(attrs={
                "placeholder": "Enter issue title",
            }),
            "description": forms.Textarea(attrs={
                "placeholder": "Describe your issue",
                "rows": 4,
            }),
            "user_name": forms.TextInput(attrs={
                "placeholder": "Enter your name",
            }),
        }


# -----------------------------
# User Registration Form
# -----------------------------
class CustomUserCreationForm(UserCreationForm):
    username = forms.CharField(
        max_length=150,
        validators=[
            RegexValidator(
                regex=r"^[a-zA-Z0-9@_]+$",
                message="Use only letters, digits, @, and _.",
            )
        ],
        help_text="Letters, digits, @ and _ are allowed.",
    )

    class Meta:
        model = User
        fields = [
            "username",
            "password1",
            "password2",
        ]


# -----------------------------
# Ticket Comment Form
# -----------------------------
class TicketCommentForm(forms.ModelForm):
    class Meta:
        model = TicketComment
        fields = ["message"]

        widgets = {
            "message": forms.Textarea(attrs={
                "placeholder": "Write a comment or update...",
                "rows": 4,
                "class": "comment-input",
            }),
        }

    def clean_message(self):
        message = self.cleaned_data["message"].strip()

        if not message:
            raise forms.ValidationError(
                "Please enter a comment."
            )

        return message


# -----------------------------
# Profile Settings Form
# -----------------------------
class UserDetailsForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = [
            "username",
            "email",
        ]

        widgets = {
            "username": forms.TextInput(attrs={
                "class": "settings-input",
                "placeholder": "Enter username",
            }),
            "email": forms.EmailInput(attrs={
                "class": "settings-input",
                "placeholder": "Enter email address",
            }),
        }


# -----------------------------
# Notification Preferences Form
# -----------------------------
class NotificationPreferencesForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            "notify_ticket_assigned",
            "notify_status_updates",
            "notify_comments",
        ]
