"""Custom exceptions for the application."""


class SalesforceAPIError(Exception):
    """Base exception for Salesforce API errors."""
    pass


class AuthenticationError(SalesforceAPIError):
    """Raised when Salesforce authentication fails."""
    pass


class APIRequestError(SalesforceAPIError):
    """Raised when a Salesforce API request fails."""
    pass


class ProcessNotFoundError(Exception):
    """Raised when a process ID is not found."""
    pass


class FileNotFoundError(Exception):
    """Raised when a file is not found."""
    pass


class GoogleDriveError(Exception):
    """Base exception for Google Drive errors."""
    pass


class GoogleDriveAuthError(GoogleDriveError):
    """Raised when Google Drive authentication fails."""
    pass


class GoogleDriveUploadError(GoogleDriveError):
    """Raised when Google Drive upload fails."""
    pass


class LucidchartError(Exception):
    """Base exception for Lucidchart errors."""
    pass


class LucidchartAuthError(LucidchartError):
    """Raised when Lucidchart authentication fails."""
    pass


class LucidchartAPIError(LucidchartError):
    """Raised when Lucidchart API request fails."""
    pass

