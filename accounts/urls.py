"""
URL configuration for accounts app.

Maps all authentication-related endpoints.
"""
from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    LogoutView,
    VerifyEmailView,
    ResendVerificationView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    CustomTokenRefreshView,
    UserProfileView,
)

app_name = 'accounts'

urlpatterns = [
    # User Registration
    path('register/', RegisterView.as_view(), name='register'),

    # Authentication
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),

    # Email Verification
    path('verify-email/', VerifyEmailView.as_view(), name='verify_email'),
    path('resend-verification/', ResendVerificationView.as_view(), name='resend_verification'),

    # Password Reset
    path('password-reset/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),

    # User Profile
    path('me/', UserProfileView.as_view(), name='user_profile'),
]
