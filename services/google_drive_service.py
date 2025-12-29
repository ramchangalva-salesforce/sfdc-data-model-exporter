"""Google Drive API service."""
import logging
import os
from typing import Optional, Dict

import requests

from config import get_settings, GOOGLE_OAUTH_URL, GOOGLE_TOKEN_URL, GOOGLE_DRIVE_UPLOAD_URL, GOOGLE_DRIVE_API_URL
from exceptions import GoogleDriveAuthError, GoogleDriveUploadError

logger = logging.getLogger(__name__)
settings = get_settings()


class GoogleDriveService:
    """Service for Google Drive operations."""
    
    def __init__(self):
        """Initialize the Google Drive service."""
        self.client_id = settings.google_client_id
        self.client_secret = settings.google_client_secret
    
    def get_auth_url(self, redirect_uri: str) -> str:
        """
        Generate Google Drive OAuth2 authorization URL.
        
        Args:
            redirect_uri: OAuth2 redirect URI
            
        Returns:
            Authorization URL
            
        Raises:
            GoogleDriveAuthError: If client ID is not configured
        """
        if not self.client_id:
            raise GoogleDriveAuthError(
                "Google Drive integration not configured. "
                "Please set GOOGLE_CLIENT_ID environment variable."
            )
        
        params = {
            'client_id': self.client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'https://www.googleapis.com/auth/drive.file',
            'access_type': 'offline',
            'prompt': 'consent'
        }
        
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"{GOOGLE_OAUTH_URL}?{query_string}"
    
    def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict[str, str]:
        """
        Exchange authorization code for access token.
        
        Args:
            code: Authorization code from OAuth2 callback
            redirect_uri: OAuth2 redirect URI
            
        Returns:
            Token response containing access_token and other tokens
            
        Raises:
            GoogleDriveAuthError: If token exchange fails
        """
        if not self.client_id or not self.client_secret:
            raise GoogleDriveAuthError(
                "Google Drive not configured. "
                "Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables."
            )
        
        token_data = {
            'code': code,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }
        
        try:
            response = requests.post(GOOGLE_TOKEN_URL, data=token_data, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"Token exchange failed: {e}")
            raise GoogleDriveAuthError(f"Failed to exchange code for token: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error during token exchange: {e}")
            raise GoogleDriveAuthError(f"Network error during token exchange: {e}")
    
    def upload_file(self, file_path: str, access_token: str) -> Dict[str, str]:
        """
        Upload a file to Google Drive.
        
        Args:
            file_path: Path to the file to upload
            access_token: Google OAuth2 access token
            
        Returns:
            Dictionary containing file_id and web_view_link
            
        Raises:
            GoogleDriveUploadError: If upload fails
        """
        if not os.path.exists(file_path):
            raise GoogleDriveUploadError(f"File not found: {file_path}")
        
        file_metadata = {'name': os.path.basename(file_path)}
        
        # Read file content
        try:
            with open(file_path, 'rb') as f:
                file_content = f.read()
        except IOError as e:
            raise GoogleDriveUploadError(f"Failed to read file: {e}")
        
        # Create multipart request
        boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
        
        # Build multipart body
        body_parts = [
            f'--{boundary}',
            'Content-Type: application/json; charset=UTF-8',
            '',
            str(file_metadata).replace("'", '"'),
            f'--{boundary}',
            'Content-Type: text/csv',
            '',
            file_content.decode('utf-8'),
            f'--{boundary}--'
        ]
        
        body = '\r\n'.join(body_parts).encode('utf-8')
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': f'multipart/related; boundary={boundary}'
        }
        
        try:
            # Upload file
            response = requests.post(
                GOOGLE_DRIVE_UPLOAD_URL,
                headers=headers,
                data=body,
                timeout=60
            )
            response.raise_for_status()
            file_data = response.json()
            file_id = file_data.get('id')
            
            # Get web view link
            file_info_url = f"{GOOGLE_DRIVE_API_URL}/{file_id}?fields=webViewLink"
            file_info_response = requests.get(
                file_info_url,
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=30
            )
            web_view_link = ''
            if file_info_response.ok:
                web_view_link = file_info_response.json().get('webViewLink', '')
            
            return {
                'file_id': file_id,
                'web_view_link': web_view_link
            }
        except requests.exceptions.HTTPError as e:
            logger.error(f"Upload failed: {e}")
            raise GoogleDriveUploadError(f"Failed to upload file to Google Drive: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error during upload: {e}")
            raise GoogleDriveUploadError(f"Network error during upload: {e}")

