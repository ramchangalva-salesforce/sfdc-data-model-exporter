"""Configuration settings for the application."""
import os
from typing import Optional
from functools import lru_cache

# Constants - defined first to avoid circular imports
# Common Salesforce instance URLs (for reference/defaults)
SALESFORCE_PRODUCTION_URL = "https://login.salesforce.com"
SALESFORCE_SANDBOX_URL = "https://test.salesforce.com"

# Salesforce API endpoint paths (these are constant across all orgs)
SALESFORCE_AUTH_URL = "/services/oauth2/authorize"
SALESFORCE_TOKEN_URL = "/services/oauth2/token"
SALESFORCE_OBJECTS_URL = "/services/data/{version}/sobjects/"
SALESFORCE_DESCRIBE_URL = "/services/data/{version}/sobjects/{object_name}/describe"
SALESFORCE_QUERY_URL = "/services/data/{version}/query"
SALESFORCE_TOOLING_QUERY_URL = "/services/data/{version}/tooling/query"
SALESFORCE_UI_API_APPS_URL = "/services/data/{version}/ui-api/apps"

# Google OAuth URLs
GOOGLE_OAUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_DRIVE_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
GOOGLE_DRIVE_API_URL = "https://www.googleapis.com/drive/v3/files"

# Lucidchart API URLs
# OAuth2 endpoints - these will show the Lucidchart login page
LUCIDCHART_OAUTH_URL = "https://lucid.app/oauth2/authorize"
LUCIDCHART_TOKEN_URL = "https://lucid.app/oauth2/token"
LUCIDCHART_API_BASE = "https://api.lucid.co/v1"
LUCIDCHART_DOCUMENTS_URL = f"{LUCIDCHART_API_BASE}/documents"

# File type constants
FILE_TYPE_METADATA = "metadata"
FILE_TYPE_LUCID = "lucid"

# Process status constants
STATUS_STARTING = "starting"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_ERROR = "error"
STATUS_TERMINATED = "terminated"
STATUS_TERMINATING = "terminating"


class Settings:
    """Application settings loaded from environment variables."""
    
    def __init__(self):
        """Initialize settings from environment variables."""
        # Application settings
        self.app_name: str = os.getenv("APP_NAME", "Salesforce Data Model Exporter")
        self.debug: bool = os.getenv("DEBUG", "False").lower() == "true"
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")
        
        # Server settings
        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = int(os.getenv("PORT", "8000"))
        
        # Google Drive OAuth2 settings
        self.google_client_id: Optional[str] = os.getenv("GOOGLE_CLIENT_ID")
        self.google_client_secret: Optional[str] = os.getenv("GOOGLE_CLIENT_SECRET")
        self.google_redirect_uri: Optional[str] = os.getenv("GOOGLE_REDIRECT_URI")
        
        # Lucidchart OAuth2 settings
        self.lucidchart_client_id: Optional[str] = os.getenv("LUCIDCHART_CLIENT_ID")
        self.lucidchart_client_secret: Optional[str] = os.getenv("LUCIDCHART_CLIENT_SECRET")
        self.lucidchart_redirect_uri: Optional[str] = os.getenv("LUCIDCHART_REDIRECT_URI")
        
        # Salesforce API settings
        self.salesforce_api_version: str = os.getenv("SALESFORCE_API_VERSION", "v53.0")
        
        # Instance URL - environment-specific defaults
        # Can be overridden via SALESFORCE_INSTANCE_URL env var
        deployment_env = os.getenv("DEPLOYMENT_ENV", "DEV").upper()
        
        if deployment_env in ("PROD", "PRODUCTION"):
            default_instance_url = SALESFORCE_PRODUCTION_URL
        elif deployment_env in ("STG", "STAGING"):
            default_instance_url = SALESFORCE_SANDBOX_URL
        else:
            # Default for DEV or unspecified - use your specific org URL
            default_instance_url = "https://cloudblazer2-dev-ed.develop.my.salesforce.com"
        
        self.salesforce_instance_url: str = os.getenv(
            "SALESFORCE_INSTANCE_URL",
            default_instance_url
        )
        
        # Salesforce OAuth2 credentials (optional - can be pre-filled in form)
        # If not set, users must enter them in the web form each time
        self.salesforce_client_id: Optional[str] = os.getenv("SALESFORCE_CLIENT_ID")
        self.salesforce_client_secret: Optional[str] = os.getenv("SALESFORCE_CLIENT_SECRET")
        self.salesforce_redirect_uri: Optional[str] = os.getenv("SALESFORCE_REDIRECT_URI")
        
        # File storage settings
        self.max_log_entries: int = int(os.getenv("MAX_LOG_ENTRIES", "1000"))
        self.input_dir: str = os.getenv("INPUT_DIR", "input")
        self.output_dir: str = os.getenv("OUTPUT_DIR", "output")


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
