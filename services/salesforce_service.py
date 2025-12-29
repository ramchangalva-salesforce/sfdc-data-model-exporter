"""Salesforce API service."""
import logging
import requests
from typing import Dict, List, Optional
from urllib.parse import quote

from config import (
    get_settings, 
    SALESFORCE_AUTH_URL, 
    SALESFORCE_TOKEN_URL, 
    SALESFORCE_OBJECTS_URL, 
    SALESFORCE_DESCRIBE_URL,
    SALESFORCE_QUERY_URL,
    SALESFORCE_TOOLING_QUERY_URL,
    SALESFORCE_UI_API_APPS_URL,
    SALESFORCE_PRODUCTION_URL,
    SALESFORCE_SANDBOX_URL
)
from exceptions import AuthenticationError, APIRequestError
from models import (
    SalesforceCredentials,
    TokenResponse,
    SalesforceObject,
    SalesforceField,
    MetadataRow,
    SalesforceApp
)

logger = logging.getLogger(__name__)
settings = get_settings()


class SalesforceService:
    """Service for interacting with Salesforce API."""
    
    def __init__(self):
        """Initialize the Salesforce service."""
        self.api_version = settings.salesforce_api_version
    
    def get_auth_url(
        self,
        instance_url: str,
        client_id: str,
        redirect_uri: str,
        state: Optional[str] = None
    ) -> str:
        """
        Generate Salesforce OAuth2 authorization URL.
        
        Args:
            instance_url: Salesforce instance URL
            client_id: Salesforce Connected App Consumer Key
            redirect_uri: OAuth2 redirect URI
            state: Optional state parameter for CSRF protection
            
        Returns:
            Authorization URL
        """
        # Ensure instance URL doesn't have trailing slash
        instance_url = instance_url.rstrip('/')
        auth_url = f"{instance_url}{SALESFORCE_AUTH_URL}"
        
        # URL-encode the redirect_uri to handle special characters
        encoded_redirect_uri = quote(redirect_uri, safe='')
        
        query_parts = [
            f"response_type=code",
            f"client_id={client_id}",
            f"redirect_uri={encoded_redirect_uri}",
            f"scope=api refresh_token offline_access"
        ]
        
        if state:
            query_parts.append(f"state={state}")
        
        query_string = '&'.join(query_parts)
        full_auth_url = f"{auth_url}?{query_string}"
        
        logger.info(f"Generated Salesforce OAuth URL for instance: {instance_url}")
        return full_auth_url
    
    def exchange_code_for_token(
        self,
        instance_url: str,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str
    ) -> TokenResponse:
        """
        Exchange authorization code for access token.
        
        Args:
            instance_url: Salesforce instance URL
            client_id: Salesforce Connected App Consumer Key
            client_secret: Salesforce Connected App Consumer Secret
            code: Authorization code from OAuth2 callback
            redirect_uri: OAuth2 redirect URI
            
        Returns:
            Token response containing access token and instance information
            
        Raises:
            AuthenticationError: If token exchange fails
        """
        # Ensure instance URL doesn't have trailing slash
        instance_url = instance_url.rstrip('/')
        
        # Determine if this is a sandbox or production org
        # Token endpoint is always login.salesforce.com or test.salesforce.com, not the instance URL
        if 'test.salesforce.com' in instance_url.lower() or 'sandbox' in instance_url.lower() or '.cs' in instance_url.lower():
            # Sandbox org
            login_url = SALESFORCE_SANDBOX_URL
        else:
            # Production org (or custom domain - use production login)
            login_url = SALESFORCE_PRODUCTION_URL
        
        token_url = f"{login_url}{SALESFORCE_TOKEN_URL}"
        
        logger.info("Exchanging authorization code for access token...")
        logger.info(f"Using login URL: {login_url}")
        
        payload = {
            'grant_type': 'authorization_code',
            'client_id': client_id,
            'client_secret': client_secret,
            'code': code,
            'redirect_uri': redirect_uri
        }
        
        try:
            # Use application/x-www-form-urlencoded content type as per Salesforce requirements
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            response = requests.post(token_url, headers=headers, data=payload, timeout=30)
            
            if not response.ok:
                error_detail = "Unknown error"
                try:
                    error_data = response.json()
                    error_detail = error_data.get('error_description', error_data.get('error', response.text))
                    logger.error(f"Token exchange failed: {error_detail}")
                    logger.error(f"Response status: {response.status_code}")
                    logger.error(f"Response body: {response.text}")
                except (ValueError, KeyError):
                    error_detail = response.text or str(response.status_code)
                    logger.error(f"Token exchange failed: {error_detail}")
                
                raise AuthenticationError(
                    f"Failed to exchange authorization code for token: {error_detail}"
                )
            
            token_data = response.json()
            logger.info("Access token retrieved successfully via OAuth2.")
            return token_data
        except AuthenticationError:
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error during token exchange: {e}")
            raise AuthenticationError(f"Network error during token exchange: {e}")
    
    def get_access_token(self, credentials: SalesforceCredentials) -> TokenResponse:
        """
        Retrieve access token from Salesforce using password flow.
        
        The token endpoint is always https://login.salesforce.com/services/oauth2/token
        for password flow, regardless of the instance URL. The instance URL is only used
        for API calls after authentication.
        
        Args:
            credentials: Salesforce authentication credentials
            
        Returns:
            Token response containing access token and instance information
            
        Raises:
            AuthenticationError: If authentication fails
        """
        # For password flow, determine the correct login URL based on instance URL
        # The instance URL in credentials is only used for API calls after auth
        # Token endpoint is always login.salesforce.com or test.salesforce.com
        # Priority order: DEV -> STG -> PROD
        instance_url = credentials.get('instance_url', '').lower()
        
        # Determine environment type from instance URL (priority: DEV -> STG -> PROD)
        is_dev_org = (
            'dev-ed' in instance_url or 
            'develop.my.salesforce.com' in instance_url or
            '.develop.' in instance_url
        )
        is_stg_org = (
            'test.salesforce.com' in instance_url or 
            'sandbox' in instance_url or 
            '.cs' in instance_url
        )
        
        # Set login URLs to try based on environment detection
        # DEV orgs (developer edition) use production login endpoint
        # STG orgs (sandbox) use test.salesforce.com login endpoint
        # PROD orgs use login.salesforce.com login endpoint
        login_urls_to_try = []
        
        if is_dev_org:
            login_urls_to_try = [SALESFORCE_PRODUCTION_URL]
            logger.info("Detected DEV org (Developer Edition) - using login.salesforce.com for authentication")
        elif is_stg_org:
            login_urls_to_try = [SALESFORCE_SANDBOX_URL, SALESFORCE_PRODUCTION_URL]
            logger.info("Detected STG org (Sandbox) - using test.salesforce.com for authentication")
        else:
            login_urls_to_try = [SALESFORCE_PRODUCTION_URL]
            logger.info("Detected PROD org (Production) - using login.salesforce.com for authentication")
        
        payload = {
            'grant_type': 'password',
            'client_id': credentials['client_id'],
            'client_secret': credentials['client_secret'],
            'username': credentials['username'],
            'password': credentials['password']
        }
        
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        last_error = None
        
        # Try each login URL
        for login_url in login_urls_to_try:
            token_url = f"{login_url}{SALESFORCE_TOKEN_URL}"
            logger.info(f"Requesting access token from Salesforce...")
            logger.info(f"Trying token endpoint: {token_url}")
            
            try:
                response = requests.post(token_url, headers=headers, data=payload, timeout=30)
                
                # If successful, return the token data
                if response.ok:
                    token_data = response.json()
                    logger.info("Access token retrieved successfully.")
                    return token_data
                
                # If not successful, extract error details
                error_detail = "Unknown error"
                try:
                    error_data = response.json()
                    error_detail = error_data.get('error_description', error_data.get('error', response.text))
                    logger.warning(f"Authentication attempt failed with {login_url}: {error_detail}")
                except (ValueError, KeyError):
                    error_detail = response.text or str(response.status_code)
                
                # Store error for final reporting
                last_error = (response.status_code, error_detail)
                
                # If this is not the last URL to try and error suggests wrong endpoint, try next
                if login_url != login_urls_to_try[-1] and response.status_code == 400:
                    logger.info(f"Trying alternative login URL...")
                    continue
                
                # Otherwise, this is a real authentication error
                break
                
            except requests.exceptions.RequestException as e:
                # Network error - if this is the last URL, raise it
                if login_url == login_urls_to_try[-1]:
                    logger.error(f"Request error during authentication: {e}")
                    raise AuthenticationError(f"Network error during authentication: {e}")
                # Otherwise, try next URL
                logger.warning(f"Network error with {login_url}, trying alternative...")
                continue
        
        # If we get here, authentication failed
        status_code, error_detail = last_error if last_error else (0, "Unknown error")
        
        # Provide detailed error messages
        logger.error(f"Salesforce authentication failed: {error_detail}")
        logger.error(f"Response status: {status_code}")
        
        if status_code == 400:
            if 'invalid_grant' in error_detail.lower() or 'authentication failure' in error_detail.lower():
                raise AuthenticationError(
                    f"Authentication failed: Invalid username or password. "
                    f"If IP restrictions are enabled, you may need to append your security token to your password. "
                    f"Error: {error_detail}"
                )
            elif 'invalid_client_id' in error_detail.lower() or 'invalid client' in error_detail.lower():
                raise AuthenticationError(
                    f"Authentication failed: Invalid Client ID (Consumer Key). "
                    f"Please verify your External Client App Consumer Key is correct. "
                    f"Error: {error_detail}"
                )
            else:
                raise AuthenticationError(
                    f"Authentication failed: {error_detail}. "
                    f"Please check your credentials and External Client App configuration."
                )
        elif status_code == 401:
            raise AuthenticationError(
                f"Unauthorized: {error_detail}. "
                f"Please verify your Client ID, Client Secret, username, and password are correct."
            )
        else:
            raise AuthenticationError(
                f"Failed to authenticate with Salesforce (Status {status_code}): {error_detail}"
            )
    
    def get_all_objects(self, access_token: str, instance_url: str) -> List[SalesforceObject]:
        """
        Retrieve all Salesforce objects using REST API.
        
        Reference: https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_list.htm
        
        Args:
            access_token: Salesforce OAuth access token
            instance_url: Salesforce instance URL (from token response)
            
        Returns:
            List of Salesforce objects
            
        Raises:
            APIRequestError: If the API request fails
        """
        # Ensure instance URL doesn't have trailing slash
        instance_url = instance_url.rstrip('/')
        
        # Use REST API endpoint: /services/data/vXX.X/sobjects/
        url = f"{instance_url}{SALESFORCE_OBJECTS_URL.format(version=self.api_version)}"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        
        logger.info(f"Retrieving all Salesforce objects from: {url}")
        
        try:
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json()
            objects = data.get('sobjects', [])
            
            # Filter out non-queryable objects and system objects
            queryable_objects = [
                obj for obj in objects 
                if obj.get('queryable', False) and not obj.get('name', '').startswith('__')
            ]
            
            logger.info(f"Retrieved {len(objects)} total objects, {len(queryable_objects)} queryable objects.")
            return queryable_objects
        except requests.exceptions.HTTPError as e:
            error_detail = ""
            try:
                error_data = response.json()
                error_detail = error_data.get('message', error_data.get('error', str(e)))
            except:
                error_detail = response.text if hasattr(response, 'text') else str(e)
            logger.error(f"Failed to retrieve objects: {error_detail}")
            raise APIRequestError(f"Failed to retrieve Salesforce objects: {error_detail}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error while retrieving objects: {e}")
            raise APIRequestError(f"Network error while retrieving objects: {e}")
    
    def get_installed_apps(self, access_token: str, instance_url: str) -> List[SalesforceApp]:
        """
        Retrieve all apps from Salesforce App Launcher using UI API.
        
        Args:
            access_token: Salesforce OAuth access token
            instance_url: Salesforce instance URL
            
        Returns:
            List of Salesforce apps with their namespace prefixes
        """
        instance_url = instance_url.rstrip('/')
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        
        apps: List[SalesforceApp] = []
        
        # Add "All Objects" option (no namespace filter)
        apps.append({
            'id': 'all',
            'name': 'All Objects',
            'label': 'All Objects (No Filter)',
            'namespacePrefix': None,
            'description': 'Extract metadata for all objects in the org'
        })
        
        try:
            # Use UI API to get all apps from App Launcher
            ui_api_url = f"{instance_url}{SALESFORCE_UI_API_APPS_URL.format(version=self.api_version)}?formFactor=Large"
            ui_response = requests.get(ui_api_url, headers=headers, timeout=60)
            
            if ui_response.ok:
                ui_data = ui_response.json()
                ui_apps = ui_data.get('apps', [])
                
                logger.info(f"Retrieved {len(ui_apps)} apps from UI API")
                
                # Process apps from UI API
                for ui_app in ui_apps:
                    app_id = ui_app.get('id', '')
                    app_label = ui_app.get('label', ui_app.get('name', 'Unknown App'))
                    app_name = ui_app.get('name', app_label)
                    
                    # Try to get namespace from app metadata or query CustomApplication
                    namespace = None
                    app_description = f"Objects from {app_label} app"
                    
                    # Query CustomApplication to get namespace if available
                    if app_id:
                        try:
                            # Escape single quotes in app_id for SOQL
                            safe_app_id = app_id.replace("'", "\\'")
                            app_query = f"SELECT Id, Name, Label, NamespacePrefix FROM CustomApplication WHERE Id = '{safe_app_id}'"
                            app_query_url = f"{instance_url}{SALESFORCE_QUERY_URL.format(version=self.api_version)}"
                            app_query_params = {'q': app_query}
                            app_query_response = requests.get(app_query_url, headers=headers, params=app_query_params, timeout=30)
                            
                            if app_query_response.ok:
                                app_query_data = app_query_response.json()
                                app_records = app_query_data.get('records', [])
                                if app_records:
                                    namespace = app_records[0].get('NamespacePrefix')
                        except Exception as e:
                            logger.debug(f"Could not get namespace for app {app_label}: {e}")
                            pass  # If query fails, continue without namespace
                    
                    # Add app (with or without namespace)
                    # For apps without namespace, we'll still show them but note they use standard objects
                    app_entry = {
                        'id': app_id or app_name,
                        'name': app_name,
                        'label': app_label,
                        'namespacePrefix': namespace,
                        'description': app_description if namespace else f"{app_label} (Standard Objects - No Namespace Filter)"
                    }
                    
                    # Only add if not already in list (check by label)
                    if not any(a['label'] == app_label for a in apps):
                        apps.append(app_entry)
            else:
                logger.warning(f"UI API request failed: {ui_response.status_code} - {ui_response.text}")
                # Fallback to CustomApplication query if UI API fails
                try:
                    app_query = "SELECT Id, Name, Label, NamespacePrefix FROM CustomApplication WHERE IsVisibleInAppLauncher = true"
                    app_url = f"{instance_url}{SALESFORCE_QUERY_URL.format(version=self.api_version)}"
                    app_params = {'q': app_query}
                    app_response = requests.get(app_url, headers=headers, params=app_params, timeout=60)
                    
                    if app_response.ok:
                        app_data = app_response.json()
                        app_records = app_data.get('records', [])
                        
                        for app_record in app_records:
                            app_namespace = app_record.get('NamespacePrefix')
                            app_label = app_record.get('Label', app_record.get('Name', 'Unknown App'))
                            app_name = app_record.get('Name', 'Unknown')
                            
                            # Add all apps, with or without namespace
                            if not any(a['label'] == app_label for a in apps):
                                apps.append({
                                    'id': app_record.get('Id', ''),
                                    'name': app_name,
                                    'label': app_label,
                                    'namespacePrefix': app_namespace,
                                    'description': f"Objects from {app_label} app" if app_namespace else f"{app_label} (Standard Objects - No Namespace Filter)"
                                })
                except Exception as e:
                    logger.warning(f"Fallback CustomApplication query also failed: {e}")
            
            # Also query InstalledSubscriberPackage for installed packages with namespaces
            try:
                package_query = "SELECT Id, SubscriberPackageId, SubscriberPackage.NamespacePrefix, SubscriberPackage.Name FROM InstalledSubscriberPackage"
                package_url = f"{instance_url}{SALESFORCE_QUERY_URL.format(version=self.api_version)}"
                package_params = {'q': package_query}
                package_response = requests.get(package_url, headers=headers, params=package_params, timeout=60)
                
                if package_response.ok:
                    package_data = package_response.json()
                    package_records = package_data.get('records', [])
                    
                    for record in package_records:
                        package_info = record.get('SubscriberPackage', {})
                        namespace = package_info.get('NamespacePrefix')
                        package_name = package_info.get('Name', 'Unknown Package')
                        
                        if namespace:
                            # Check if already added from UI API
                            if not any(a['namespacePrefix'] == namespace for a in apps):
                                apps.append({
                                    'id': record.get('Id', ''),
                                    'name': namespace,
                                    'label': f"{package_name} ({namespace})",
                                    'namespacePrefix': namespace,
                                    'description': f"Objects from {package_name} package"
                                })
            except Exception as e:
                logger.warning(f"Error querying installed packages: {e}")
            
            # Sort apps: All Objects first, then by label
            apps = [apps[0]] + sorted([a for a in apps[1:] if a['label'] != 'All Objects (No Filter)'], key=lambda x: x['label'])
            
            logger.info(f"Retrieved {len(apps)} apps from App Launcher")
            return apps
            
        except requests.exceptions.HTTPError as e:
            error_detail = ""
            try:
                error_data = response.json()
                error_detail = error_data.get('message', error_data.get('error', str(e)))
            except:
                error_detail = response.text if hasattr(response, 'text') else str(e)
            logger.warning(f"Failed to retrieve apps (continuing with all objects): {error_detail}")
            # Return at least the "All Objects" option
            return apps
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request error while retrieving apps (continuing with all objects): {e}")
            return apps
    
    def get_object_fields(
        self, 
        access_token: str, 
        instance_url: str, 
        object_name: str
    ) -> List[SalesforceField]:
        """
        Retrieve fields for a specific Salesforce object using REST API describe endpoint.
        
        Reference: https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_list.htm
        
        Args:
            access_token: Salesforce OAuth access token
            instance_url: Salesforce instance URL (from token response)
            object_name: Name of the Salesforce object
            
        Returns:
            List of field metadata for the object
            
        Raises:
            APIRequestError: If the API request fails
        """
        # Ensure instance URL doesn't have trailing slash
        instance_url = instance_url.rstrip('/')
        
        # Use REST API describe endpoint: /services/data/vXX.X/sobjects/{ObjectName}/describe/
        url = f"{instance_url}{SALESFORCE_DESCRIBE_URL.format(version=self.api_version, object_name=object_name)}"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        
        logger.debug(f"Retrieving fields for object: {object_name} from: {url}")
        
        try:
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json()
            
            # The describe response has 'fields' at the root level
            fields = data.get('fields', [])
            
            # Filter out system fields that aren't useful for data modeling
            # Keep all fields but we can filter in extract_metadata if needed
            logger.debug(f"Retrieved {len(fields)} fields for object: {object_name}.")
            return fields
        except requests.exceptions.HTTPError as e:
            error_detail = ""
            try:
                error_data = response.json()
                error_detail = error_data.get('message', error_data.get('error', str(e)))
            except:
                error_detail = response.text if hasattr(response, 'text') else str(e)
            logger.error(f"Failed to retrieve fields for {object_name}: {error_detail}")
            raise APIRequestError(f"Failed to retrieve fields for {object_name}: {error_detail}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error while retrieving fields for {object_name}: {e}")
            raise APIRequestError(f"Network error while retrieving fields for {object_name}: {e}")
    
    def extract_metadata(
        self,
        access_token: str,
        instance_url: str,
        objects: List[SalesforceObject],
        should_continue = None,
        log_callback = None,
        namespace_prefix: Optional[str] = None
    ) -> List[MetadataRow]:
        """
        Extract metadata for all objects and their fields using Salesforce REST API.
        
        Reference: https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_list.htm
        
        Args:
            access_token: Salesforce OAuth access token
            instance_url: Salesforce instance URL (from token response)
            objects: List of Salesforce objects to process
            should_continue: Optional callback to check if processing should continue
            log_callback: Optional callback function(message: str) to log progress messages
            namespace_prefix: Optional namespace prefix to filter objects (e.g., 'ns' for objects like ns__CustomObject__c)
            
        Returns:
            List of metadata rows
        """
        metadata_rows: List[MetadataRow] = []
        
        # Filter objects by namespace prefix if provided
        # Note: namespace_prefix can be None, 'all', or an actual namespace
        # Apps without namespace will have 'all' as value, so they extract all objects
        if namespace_prefix and namespace_prefix.strip() and namespace_prefix != 'all':
            namespace_prefix = namespace_prefix.strip()
            
            # Filter by namespace prefix - objects with this namespace
            filtered_objects = [
                obj for obj in objects 
                if obj.get('name', '').startswith(f"{namespace_prefix}__")
            ]
            if log_callback:
                log_callback(f"Filtering objects by app namespace '{namespace_prefix}': {len(filtered_objects)} objects found")
                if len(filtered_objects) == 0:
                    log_callback(f"Warning: No objects found with namespace '{namespace_prefix}'. This app may not have custom objects with this namespace.")
                    log_callback(f"Available objects sample: {', '.join([obj.get('name', '') for obj in objects[:10]])}")
        else:
            filtered_objects = objects
            if log_callback:
                if namespace_prefix and namespace_prefix == 'all':
                    log_callback("No namespace filter applied - extracting all objects")
                else:
                    log_callback("Extracting all objects (no app filter)")
        
        total_objects = len(filtered_objects)
        processed_count = 0
        
        for obj in filtered_objects:
            # Check if processing should continue
            if should_continue and not should_continue():
                message = "Processing terminated by user."
                logger.info(message)
                if log_callback:
                    log_callback(message)
                break
            
            object_name = obj.get('name')
            if not object_name:
                continue
            
            processed_count += 1
            message = f"Processing object {processed_count}/{total_objects}: {object_name}"
            logger.info(message)
            if log_callback:
                log_callback(message)
            
            try:
                fields = self.get_object_fields(access_token, instance_url, object_name)
                
                for field in fields:
                    field_name = field.get('name')
                    if not field_name:
                        continue
                    
                    # Extract relationship information
                    reference_to = field.get('referenceTo', [])
                    relationship_name = field.get('relationshipName', '')
                    
                    # Build metadata row
                    metadata_rows.append({
                        'Object': object_name,
                        'Field': field_name,
                        'Type': field.get('type', 'N/A'),
                        'Length': str(field.get('length', 'N/A')) if field.get('length') else 'N/A',
                        'Precision': str(field.get('precision', 'N/A')) if field.get('precision') else 'N/A',
                        'Scale': str(field.get('scale', 'N/A')) if field.get('scale') else 'N/A',
                        'ReferenceTo': ','.join(reference_to) if reference_to else 'N/A',
                        'RelationshipName': relationship_name if relationship_name else 'N/A'
                    })
                    
            except APIRequestError as e:
                logger.warning(f"Error processing object {object_name}: {e}")
                continue
            except Exception as e:
                logger.warning(f"Unexpected error processing object {object_name}: {e}")
                continue
        
        completion_message = f"Metadata extraction completed. Processed {processed_count} objects, extracted {len(metadata_rows)} field records."
        logger.info(completion_message)
        if log_callback:
            log_callback(completion_message)
        return metadata_rows

