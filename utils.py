"""Utility functions."""
import logging
from typing import Dict, Optional
from urllib.parse import urlparse

from config import get_settings, STATUS_STARTING, STATUS_RUNNING, STATUS_COMPLETED, STATUS_ERROR, STATUS_TERMINATED
from models import ProcessData

logger = logging.getLogger(__name__)
settings = get_settings()


def get_redirect_uri(request_base_url: str, configured_uri: Optional[str] = None, callback_path: str = "/google-drive-callback") -> str:
    """
    Get OAuth2 redirect URI from configuration or construct from request.
    
    Args:
        request_base_url: Base URL from the request
        configured_uri: Pre-configured redirect URI from settings
        callback_path: Callback path (default: /google-drive-callback)
        
    Returns:
        Redirect URI string
    """
    if configured_uri:
        return configured_uri
    
    # Construct from request URL
    base_url = str(request_base_url).rstrip('/')
    return f"{base_url}{callback_path}"


def create_process_data() -> ProcessData:
    """
    Create a new process data structure.
    
    Returns:
        Initialized process data dictionary
    """
    from datetime import datetime
    return {
        'status': STATUS_STARTING,
        'logs': [],
        'created_at': datetime.now().isoformat()
    }


def validate_file_type(file_type: str) -> bool:
    """
    Validate file type parameter.
    
    Args:
        file_type: File type to validate
        
    Returns:
        True if valid, False otherwise
    """
    from config import FILE_TYPE_METADATA, FILE_TYPE_LUCID
    return file_type in (FILE_TYPE_METADATA, FILE_TYPE_LUCID)

