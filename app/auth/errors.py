"""Authentication domain exceptions."""
from __future__ import annotations

from app.models.errors import NexaError


class AuthError(NexaError):
    """Base auth error."""

    default_message = "Authentication failed."
    code = "AuthError"


class EmailAlreadyRegisteredError(AuthError):
    default_message = "An account with this email already exists."
    code = "EmailAlreadyRegistered"


class UsernameTakenError(AuthError):
    default_message = "This username is already taken. If this is your account, sign in instead."
    code = "UsernameTaken"


class InvalidCredentialsError(AuthError):
    default_message = "Invalid email or password."
    code = "InvalidCredentials"


class EmailNotVerifiedError(AuthError):
    default_message = "Email address is not verified."
    code = "EmailNotVerified"


class AccountNotActiveError(AuthError):
    default_message = "Account is not active."
    code = "AccountNotActive"


class ConsentRequiredError(AuthError):
    default_message = "All required consents must be accepted."
    code = "ConsentRequired"


class PasswordMismatchError(AuthError):
    default_message = "Passwords do not match."
    code = "PasswordMismatch"


class WeakPasswordError(AuthError):
    default_message = "Password does not meet security requirements."
    code = "WeakPassword"


class InvalidVerificationCodeError(AuthError):
    default_message = "Invalid verification code."
    code = "InvalidVerificationCode"


class VerificationCodeExpiredError(AuthError):
    default_message = "Verification code has expired."
    code = "VerificationCodeExpired"


class VerificationAttemptsExceededError(AuthError):
    default_message = "Too many verification attempts. Request a new code."
    code = "VerificationAttemptsExceeded"


class VerificationResendCooldownError(AuthError):
    default_message = "Please wait before requesting another code."
    code = "VerificationResendCooldown"

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(
            f"Please wait {retry_after_seconds} seconds before requesting another code."
        )
        self.retry_after_seconds = retry_after_seconds


class UnauthorizedError(AuthError):
    default_message = "Authentication required."
    code = "Unauthorized"


class SessionInvalidError(AuthError):
    default_message = "Session is invalid or expired."
    code = "SessionInvalid"


class ValidationAuthError(AuthError):
    default_message = "Invalid registration data."
    code = "ValidationError"


class RegistrationClosedError(AuthError):
    default_message = "Registration is closed. This NEXA instance has a single owner account."
    code = "RegistrationClosed"


class OAuthStateInvalidError(AuthError):
    default_message = "OAuth state is invalid or expired."
    code = "OAuthStateInvalid"


class DeviceLoginError(AuthError):
    default_message = "Device login failed."
    code = "DeviceLoginError"


class DeviceLoginPendingError(AuthError):
    default_message = "Device login is still pending."
    code = "authorization_pending"


class PasskeyError(AuthError):
    default_message = "Passkey authentication failed."
    code = "PasskeyError"


class AccountDeleteConfirmError(AuthError):
    default_message = "Type DELETE to confirm permanent account deletion."
    code = "AccountDeleteConfirmRequired"
