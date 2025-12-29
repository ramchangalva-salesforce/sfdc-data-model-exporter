"""Lucidchart API service."""
import logging
from typing import Dict, List, Optional

import requests

from config import (
    get_settings,
    LUCIDCHART_OAUTH_URL,
    LUCIDCHART_TOKEN_URL,
    LUCIDCHART_DOCUMENTS_URL
)
from exceptions import LucidchartError, LucidchartAuthError, LucidchartAPIError

logger = logging.getLogger(__name__)
settings = get_settings()


class LucidchartService:
    """Service for Lucidchart operations."""
    
    def __init__(self):
        """Initialize the Lucidchart service."""
        self.client_id = settings.lucidchart_client_id
        self.client_secret = settings.lucidchart_client_secret
    
    def get_auth_url(self, redirect_uri: str, state: Optional[str] = None) -> str:
        """
        Generate Lucidchart OAuth2 authorization URL.
        
        Args:
            redirect_uri: OAuth2 redirect URI
            state: Optional state parameter for CSRF protection
            
        Returns:
            Authorization URL
            
        Raises:
            LucidchartAuthError: If client ID is not configured
        """
        if not self.client_id:
            raise LucidchartAuthError(
                "Lucidchart integration not configured. "
                "Please set LUCIDCHART_CLIENT_ID environment variable."
            )
        
        # Lucidchart OAuth2 parameters
        # Using proper scopes for Lucidchart API access
        params = {
            'client_id': self.client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'lucidchart.document.content offline_access user.profile',
            'state': state or ''
        }
        
        # Build query string, filtering out empty values
        query_parts = []
        for k, v in params.items():
            if v:
                query_parts.append(f"{k}={v}")
        
        query_string = '&'.join(query_parts)
        auth_url = f"{LUCIDCHART_OAUTH_URL}?{query_string}"
        
        logger.info(f"Generated Lucidchart OAuth URL: {auth_url}")
        return auth_url
    
    def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict[str, str]:
        """
        Exchange authorization code for access token.
        
        Args:
            code: Authorization code from OAuth2 callback
            redirect_uri: OAuth2 redirect URI
            
        Returns:
            Token response containing access_token and other tokens
            
        Raises:
            LucidchartAuthError: If token exchange fails
        """
        if not self.client_id or not self.client_secret:
            raise LucidchartAuthError(
                "Lucidchart not configured. "
                "Please set LUCIDCHART_CLIENT_ID and LUCIDCHART_CLIENT_SECRET environment variables."
            )
        
        # Lucidchart uses form-encoded POST request (not Basic Auth)
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        token_data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        try:
            response = requests.post(LUCIDCHART_TOKEN_URL, headers=headers, data=token_data, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"Token exchange failed: {e}")
            error_detail = response.text if hasattr(response, 'text') else str(e)
            raise LucidchartAuthError(f"Failed to exchange code for token: {error_detail}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error during token exchange: {e}")
            raise LucidchartAuthError(f"Network error during token exchange: {e}")
    
    def get_documents(self, access_token: str) -> List[Dict]:
        """
        Get list of user's Lucidchart documents.
        
        Args:
            access_token: Lucidchart OAuth2 access token
            
        Returns:
            List of document dictionaries
            
        Raises:
            LucidchartAPIError: If API request fails
        """
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(LUCIDCHART_DOCUMENTS_URL, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get('data', [])
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to get documents: {e}")
            raise LucidchartAPIError(f"Failed to retrieve documents: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error while getting documents: {e}")
            raise LucidchartAPIError(f"Network error while retrieving documents: {e}")
    
    def get_document_embed_url(self, document_id: str, access_token: str) -> str:
        """
        Get embed URL for a Lucidchart document.
        
        Args:
            document_id: Lucidchart document ID
            access_token: Lucidchart OAuth2 access token
            
        Returns:
            Embed URL for the document
        """
        # Lucidchart embed URL format
        return f"https://lucid.app/documents/view/{document_id}"
    
    def create_document_from_csv(
        self,
        csv_content: str,
        document_name: str,
        access_token: str
    ) -> Dict[str, str]:
        """
        Create a new Lucidchart document from CSV data.
        
        Note: This is a placeholder. Lucidchart API may require specific format
        or may need to be done through their import feature.
        
        Args:
            csv_content: CSV file content
            document_name: Name for the new document
            access_token: Lucidchart OAuth2 access token
            
        Returns:
            Dictionary with document_id and embed_url
            
        Raises:
            LucidchartAPIError: If document creation fails
        """
        # Note: Lucidchart's API may not directly support CSV import
        # This would typically be done through their web interface
        # For now, we'll create a document and provide instructions
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Create a new document
        document_data = {
            'title': document_name,
            'type': 'chart'
        }
        
        try:
            response = requests.post(
                LUCIDCHART_DOCUMENTS_URL,
                headers=headers,
                json=document_data,
                timeout=30
            )
            response.raise_for_status()
            doc = response.json()
            document_id = doc.get('id')
            
            return {
                'document_id': document_id,
                'embed_url': self.get_document_embed_url(document_id, access_token),
                'message': 'Document created. Please use Lucidchart import feature to add CSV data.'
            }
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to create document: {e}")
            raise LucidchartAPIError(f"Failed to create document: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error during document creation: {e}")
            raise LucidchartAPIError(f"Network error during document creation: {e}")

