from __future__ import annotations

from dataclasses import dataclass


class ProvisioningError(RuntimeError):
    """Base exception for expected provisioning failures."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        if self.hint:
            return f"{self.message}\nHint: {self.hint}"
        return self.message


class ConfigurationError(ProvisioningError):
    pass


class CsvValidationError(ProvisioningError):
    pass


class AuthenticationError(ProvisioningError):
    pass


class AuthorizationError(ProvisioningError):
    pass


class ResourceNotFoundError(ProvisioningError):
    pass


class ConflictError(ProvisioningError):
    pass


class RateLimitError(ProvisioningError):
    pass


class WorkflowPausedError(ProvisioningError):
    """Used when external/eventual-consistency work must complete before continuing."""


@dataclass(slots=True)
class ApiFailure:
    status_code: int
    method: str
    url: str
    response_body: str


class AtlassianApiError(ProvisioningError):
    def __init__(
        self,
        message: str,
        failure: ApiFailure,
        hint: str | None = None,
    ) -> None:
        super().__init__(message, hint)
        self.failure = failure
