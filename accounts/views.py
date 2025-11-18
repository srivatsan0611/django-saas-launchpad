import uuid
from rest_framework import status, generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.exceptions import TokenError

from .models import User
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    UserSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    EmailVerificationSerializer,
    RequestMagicLinkSerializer,
    VerifyMagicLinkSerializer,
)


class RegisterView(generics.CreateAPIView):
    """
    POST /api/auth/register/

    User registration endpoint.
    Creates a new user account and generates email verification token.
    Returns user data with 201 status.
    """
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                'message': 'User registered successfully. Please check your email to verify your account.',
                'user': UserSerializer(user).data
            },
            status=status.HTTP_201_CREATED
        )


class LoginView(APIView):
    """
    POST /api/auth/login/

    User login endpoint.
    Validates credentials and returns JWT access and refresh tokens.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)

        return Response({
            'message': 'Login successful.',
            'user': UserSerializer(user).data,
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }
        }, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """
    POST /api/auth/logout/

    User logout endpoint.
    Blacklists the provided refresh token.
    Requires authentication.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh_token')

            if not refresh_token:
                return Response(
                    {'error': 'Refresh token is required.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Blacklist the refresh token
            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response(
                {'message': 'Logout successful.'},
                status=status.HTTP_200_OK
            )
        except TokenError:
            return Response(
                {'error': 'Invalid token.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception:
            return Response(
                {'error': 'An error occurred during logout.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VerifyEmailView(APIView):
    """
    POST /api/auth/verify-email/

    Email verification endpoint.
    Verifies user's email address using the provided token.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                'message': 'Email verified successfully.',
                'user': UserSerializer(user).data
            },
            status=status.HTTP_200_OK
        )


class ResendVerificationView(APIView):
    """
    POST /api/auth/resend-verification/

    Resend email verification link.
    Generates a new verification token and sends email.
    Requires user email in request body.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')

        if not email:
            return Response(
                {'error': 'Email is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)

            if user.email_verified:
                return Response(
                    {'message': 'Email is already verified.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Generate new verification token
            new_token = str(uuid.uuid4())
            user.email_verification_token = new_token
            user.save()

            # Trigger send_verification_email Celery task
            from accounts.tasks import send_verification_email
            send_verification_email.delay(user.id, new_token)

            return Response(
                {'message': 'Verification email sent successfully.'},
                status=status.HTTP_200_OK
            )
        except User.DoesNotExist:
            # Don't reveal if user exists for security
            return Response(
                {'message': 'If an account with that email exists, a verification email has been sent.'},
                status=status.HTTP_200_OK
            )


class PasswordResetRequestView(APIView):
    """
    POST /api/auth/password-reset/

    Password reset request endpoint.
    Sends password reset email with token.
    Requires user email in request body.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {'message': 'If an account with that email exists, a password reset link has been sent.'},
            status=status.HTTP_200_OK
        )


class PasswordResetConfirmView(APIView):
    """
    POST /api/auth/password-reset/confirm/

    Password reset confirmation endpoint.
    Resets user's password using the provided token and new password.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                'message': 'Password reset successful. You can now login with your new password.',
                'user': UserSerializer(user).data
            },
            status=status.HTTP_200_OK
        )


class CustomTokenRefreshView(TokenRefreshView):
    """
    POST /api/auth/token/refresh/

    JWT token refresh endpoint.
    Uses simplejwt's built-in TokenRefreshView.
    Accepts refresh token and returns new access token.
    """
    permission_classes = [permissions.AllowAny]


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    GET/PATCH /api/auth/me/

    User profile endpoint.
    GET: Returns authenticated user's profile data.
    PATCH: Updates authenticated user's profile data.
    Requires authentication.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """Return the authenticated user."""
        return self.request.user


class RequestMagicLinkView(APIView):
    """
    POST /api/auth/magic-link/

    Request magic link endpoint.
    Sends a passwordless authentication link to user's email.
    Magic link expires in 15 minutes.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RequestMagicLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {'message': 'If an account with that email exists, a magic link has been sent.'},
            status=status.HTTP_200_OK
        )


class VerifyMagicLinkView(APIView):
    """
    POST /api/auth/magic-link/verify/

    Verify magic link endpoint.
    Validates the magic link token and returns JWT access and refresh tokens.
    Marks the magic link as used after successful verification.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifyMagicLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)

        return Response({
            'message': 'Magic link verified successfully.',
            'user': UserSerializer(user).data,
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }
        }, status=status.HTTP_200_OK)
