import uuid
from datetime import timedelta
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers
from .models import User, MagicLink


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for user data retrieval.
    Returns safe user information without sensitive fields.
    """

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'email_verified',
            'created_at',
        ]
        read_only_fields = ['id', 'email_verified', 'created_at']


class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.
    Handles user signup with email, password validation, and generates verification token.
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )

    class Meta:
        model = User
        fields = [
            'email',
            'password',
            'password_confirm',
            'first_name',
            'last_name',
        ]
        extra_kwargs = {
            'first_name': {'required': False},
            'last_name': {'required': False},
        }

    def validate(self, attrs):
        """
        Validate that password and password_confirm match.
        """
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                "password_confirm": "Password fields didn't match."
            })
        return attrs

    def create(self, validated_data):
        """
        Create a new user with hashed password and generate email verification token.
        """
        # Remove password_confirm from validated data
        validated_data.pop('password_confirm')

        # Generate email verification token
        email_verification_token = str(uuid.uuid4())

        # Create user
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            email_verification_token=email_verification_token,
            email_verified=False,
        )

        # Trigger send_verification_email Celery task
        from accounts.tasks import send_verification_email
        send_verification_email.delay(user.id, email_verification_token)

        return user


class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login.
    Validates credentials and returns authenticated user object.
    """
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate(self, attrs):
        """
        Validate user credentials using Django's authenticate method.
        """
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            # Authenticate user
            user = authenticate(
                request=self.context.get('request'),
                username=email,  # USERNAME_FIELD is email
                password=password
            )

            if not user:
                raise serializers.ValidationError(
                    'Unable to log in with provided credentials.',
                    code='authorization'
                )

            if not user.is_active:
                raise serializers.ValidationError(
                    'User account is disabled.',
                    code='authorization'
                )

            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError(
                'Must include "email" and "password".',
                code='authorization'
            )


class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Serializer for password reset request.
    Takes email and generates reset token with 24h expiry.
    """
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        """
        Validate that a user with this email exists.
        """
        try:
            user = User.objects.get(email=value)
        except User.DoesNotExist:
            # Don't reveal whether a user exists or not for security
            # But we still validate the email format
            pass
        return value

    def save(self):
        """
        Generate password reset token and set expiry.
        """
        email = self.validated_data['email']

        try:
            user = User.objects.get(email=email)

            # Generate reset token
            reset_token = str(uuid.uuid4())

            # Set token and expiry (24 hours from now)
            user.password_reset_token = reset_token
            user.password_reset_token_expires_at = timezone.now() + timedelta(hours=24)
            user.save()

            # Trigger send_password_reset_email Celery task
            from accounts.tasks import send_password_reset_email
            send_password_reset_email.delay(user.id, reset_token)

            return user
        except User.DoesNotExist:
            # Silently fail for security (don't reveal if user exists)
            return None


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Serializer for password reset confirmation.
    Takes token and new password, validates and resets password.
    """
    token = serializers.CharField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate(self, attrs):
        """
        Validate that passwords match and token is valid.
        """
        # Check passwords match
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                "password_confirm": "Password fields didn't match."
            })

        # Validate token
        token = attrs.get('token')
        try:
            user = User.objects.get(password_reset_token=token)

            # Check if token has expired
            if user.password_reset_token_expires_at < timezone.now():
                raise serializers.ValidationError({
                    "token": "Password reset token has expired."
                })

            attrs['user'] = user
        except User.DoesNotExist:
            raise serializers.ValidationError({
                "token": "Invalid password reset token."
            })

        return attrs

    def save(self):
        """
        Reset the user's password and clear the reset token.
        """
        user = self.validated_data['user']
        password = self.validated_data['password']

        # Set new password
        user.set_password(password)

        # Clear reset token and expiry
        user.password_reset_token = None
        user.password_reset_token_expires_at = None
        user.save()

        return user


class EmailVerificationSerializer(serializers.Serializer):
    """
    Serializer for email verification.
    Takes token and marks email as verified.
    """
    token = serializers.CharField(required=True)

    def validate_token(self, value):
        """
        Validate that the token exists and belongs to an unverified user.
        """
        try:
            user = User.objects.get(email_verification_token=value)

            if user.email_verified:
                raise serializers.ValidationError(
                    "Email is already verified."
                )

            self.user = user
        except User.DoesNotExist:
            raise serializers.ValidationError(
                "Invalid verification token."
            )

        return value

    def save(self):
        """
        Mark the user's email as verified and clear the verification token.
        """
        self.user.email_verified = True
        self.user.email_verification_token = None
        self.user.save()

        return self.user


class RequestMagicLinkSerializer(serializers.Serializer):
    """
    Serializer for requesting a magic link.
    Takes email and creates a magic link for passwordless authentication.
    """
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        """
        Validate that a user with this email exists.
        """
        try:
            user = User.objects.get(email=value)
            if not user.is_active:
                raise serializers.ValidationError(
                    "User account is disabled."
                )
        except User.DoesNotExist:
            # Don't reveal whether a user exists or not for security
            # But we still validate the email format
            pass
        return value

    def save(self):
        """
        Create a magic link for the user.
        """
        email = self.validated_data['email']

        try:
            user = User.objects.get(email=email)

            # Create magic link
            magic_link = MagicLink.objects.create(user=user)

            # Trigger send_magic_link_email Celery task
            from accounts.tasks import send_magic_link_email
            send_magic_link_email.delay(magic_link.id)

            return magic_link
        except User.DoesNotExist:
            # Silently fail for security (don't reveal if user exists)
            return None


class VerifyMagicLinkSerializer(serializers.Serializer):
    """
    Serializer for verifying a magic link.
    Validates token and returns authenticated user.
    """
    token = serializers.UUIDField(required=True)

    def validate_token(self, value):
        """
        Validate that the magic link token is valid.
        """
        try:
            magic_link = MagicLink.objects.get(token=value)

            if magic_link.is_used:
                raise serializers.ValidationError(
                    "This magic link has already been used."
                )

            if magic_link.is_expired():
                raise serializers.ValidationError(
                    "This magic link has expired."
                )

            if not magic_link.user.is_active:
                raise serializers.ValidationError(
                    "User account is disabled."
                )

            self.magic_link = magic_link
        except MagicLink.DoesNotExist:
            raise serializers.ValidationError(
                "Invalid magic link token."
            )

        return value

    def save(self):
        """
        Mark the magic link as used and return the user.
        """
        self.magic_link.is_used = True
        self.magic_link.save()

        return self.magic_link.user
