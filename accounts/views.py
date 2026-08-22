"""
accounts/views.py
Handles user registration, login, and logout.
Uses Django's built-in authentication system.
"""

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from .forms import RegisterForm


def register_view(request):
    """
    Register a new user.
    GET  → show empty registration form
    POST → validate and create user, then log them in
    """
    if request.user.is_authenticated:
        return redirect('/trades/dashboard/')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()  # Save new user to database
            login(request, user)  # Log them in automatically
            messages.success(request, f'Welcome, {user.username}! Your account is ready.')
            return redirect('/trades/dashboard/')
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    """
    Log in an existing user.
    GET  → show empty login form
    POST → validate credentials and log in
    """
    if request.user.is_authenticated:
        return redirect('/trades/dashboard/')

    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect('/trades/dashboard/')
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = AuthenticationForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    """Log out the current user and redirect to login page."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('/accounts/login/')
