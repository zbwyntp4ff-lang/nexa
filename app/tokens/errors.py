"""Token / credits domain errors."""
from __future__ import annotations

from app.models.errors import NexaError


class TokenError(NexaError):
    default_message = "Token operation failed."
    code = "TokenError"


class InsufficientTokensError(TokenError):
    default_message = "Insufficient token balance."
    code = "InsufficientTokens"

    def __init__(self, balance: int = 0, required: int = 0) -> None:
        super().__init__(
            f"Insufficient tokens: balance={balance}, required={required}."
        )
        self.balance = balance
        self.required = required


class DailyTokenLimitError(TokenError):
    default_message = "Daily token limit exceeded."
    code = "DailyTokenLimitExceeded"

    def __init__(self, used: int = 0, limit: int = 0) -> None:
        super().__init__(f"Daily token limit exceeded: used={used}, limit={limit}.")
        self.used = used
        self.limit = limit


class MonthlyTokenLimitError(TokenError):
    default_message = "Monthly token limit exceeded."
    code = "MonthlyTokenLimitExceeded"

    def __init__(self, used: int = 0, limit: int = 0) -> None:
        super().__init__(f"Monthly token limit exceeded: used={used}, limit={limit}.")
        self.used = used
        self.limit = limit


class TokenAdminRequiredError(TokenError):
    default_message = "Administrator privileges required."
    code = "TokenAdminRequired"


class InvalidTokenAmountError(TokenError):
    default_message = "Token amount must be a positive integer."
    code = "InvalidTokenAmount"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.default_message)


class NegativeBalanceError(TokenError):
    """Internal invariant — should never surface if atomic debit is correct."""

    default_message = "Token balance cannot be negative."
    code = "NegativeBalance"
