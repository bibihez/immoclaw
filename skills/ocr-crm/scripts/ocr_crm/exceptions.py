class OcrCrmError(Exception):
    """Base error for the OCR CRM package."""


class ConfigurationError(OcrCrmError):
    """Raised when required runtime configuration is missing."""


class ValidationError(OcrCrmError):
    """Raised when a draft cannot be pushed safely."""


class ExternalServiceError(OcrCrmError):
    """Raised when an external provider call fails."""
