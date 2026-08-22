"""
accounts/forms.py
Custom registration form that extends Django's built-in UserCreationForm.
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class RegisterForm(UserCreationForm):
    """
    Registration form with email field added.
    Inherits username + password fields from UserCreationForm.
    """
    # Override username to remove Django's default ugly help text
    username = forms.CharField(
        max_length=30,
        help_text='Choose a username. Letters, numbers, and underscores only.',
        widget=forms.TextInput(attrs={'placeholder': 'e.g. john_trader'})
    )

    email = forms.EmailField(
        required=True,
        help_text='We will never share your email.',
        widget=forms.EmailInput(attrs={'placeholder': 'e.g. john@email.com'})
    )

    password1 = forms.CharField(
        label='Password',
        help_text='At least 8 characters.',
        widget=forms.PasswordInput(attrs={'placeholder': 'Create a password'})
    )

    password2 = forms.CharField(
        label='Confirm Password',
        help_text='Enter the same password again.',
        widget=forms.PasswordInput(attrs={'placeholder': 'Repeat your password'})
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def save(self, commit=True):
        """Override save to also store the email address."""
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user