"""Main FastAPI application entry point."""
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, Optional

from fastapi import FastAPI, Request, Form, BackgroundTasks, HTTPException, Body
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from jinja2 import Environment, FileSystemLoader

from config import get_settings, FILE_TYPE_METADATA, FILE_TYPE_LUCID
from exceptions import (
    ProcessNotFoundError,
    FileNotFoundError,
    GoogleDriveAuthError,
    GoogleDriveUploadError,
    AuthenticationError,
    APIRequestError
)
from models import ProcessData, SalesforceCredentials
from services.salesforce_service import SalesforceService
from services.file_service import FileService
from services.google_drive_service import GoogleDriveService
from services.lucidchart_service import (
    LucidchartService,
    LucidchartAuthError,
    LucidchartAPIError
)
from utils import get_redirect_uri, create_process_data, validate_file_type

# Configure logging
logging.basicConfig(
    level=get_settings().log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
settings = get_settings()
app = FastAPI(title=settings.app_name)

# Add CORS middleware for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup templates and static files
templates = Environment(loader=FileSystemLoader("templates"))
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize services
salesforce_service = SalesforceService()
file_service = FileService()
google_drive_service = GoogleDriveService()
lucidchart_service = LucidchartService()

# Store running processes and their logs
processes: Dict[str, ProcessData] = {}
running_flags: Dict[str, bool] = {}


def add_log(process_id: str, message: str) -> None:
    """
    Add a log message to the process logs.
    
    Args:
        process_id: Process identifier
        message: Log message to add
    """
    if process_id in processes:
        processes[process_id]['logs'].append(message)
        # Keep only last N log entries
        max_entries = settings.max_log_entries
        if len(processes[process_id]['logs']) > max_entries:
            processes[process_id]['logs'] = processes[process_id]['logs'][-max_entries:]


def run_process_task(
    process_id: str,
    credentials: SalesforceCredentials
) -> None:
    """
    Background task to run the Salesforce metadata extraction using password flow.
    
    Args:
        process_id: Process identifier
        credentials: Salesforce authentication credentials
    """
    from config import STATUS_RUNNING, STATUS_COMPLETED, STATUS_ERROR, STATUS_TERMINATED
    
    running_flags[process_id] = True
    processes[process_id]['status'] = STATUS_RUNNING
    
    try:
        add_log(process_id, "Starting metadata retrieval process...")
        
        # Get access token
        try:
            token_response = salesforce_service.get_access_token(credentials)
            access_token = token_response['access_token']
            # Use instance_url from token response (this is the correct instance URL from Salesforce)
            # Fallback to provided instance_url if not in response
            instance_url = token_response.get('instance_url') or credentials['instance_url']
            add_log(process_id, "Access token retrieved successfully.")
            add_log(process_id, f"Using Salesforce instance: {instance_url}")
        except AuthenticationError as auth_error:
            error_msg = str(auth_error)
            add_log(process_id, f"Authentication error: {error_msg}")
            raise  # Re-raise to be caught by outer exception handler
        
        # Continue with metadata extraction
        namespace_prefix = processes[process_id].get('namespace_prefix')
        _run_metadata_extraction(process_id, access_token, instance_url, namespace_prefix)
        
    except Exception as e:
        error_msg = f"An error occurred: {str(e)}"
        logger.exception(f"Error in process {process_id}: {e}")
        add_log(process_id, error_msg)
        processes[process_id]['status'] = STATUS_ERROR
        processes[process_id]['error'] = str(e)
    finally:
        running_flags[process_id] = False


def run_process_task_with_token(
    process_id: str,
    access_token: str,
    instance_url: str
) -> None:
    """
    Background task to run the Salesforce metadata extraction using OAuth2 access token.
    
    Args:
        process_id: Process identifier
        access_token: Salesforce OAuth2 access token
        instance_url: Salesforce instance URL
    """
    from config import STATUS_RUNNING, STATUS_COMPLETED, STATUS_ERROR, STATUS_TERMINATED
    
    running_flags[process_id] = True
    processes[process_id]['status'] = STATUS_RUNNING
    
    try:
        add_log(process_id, "Starting metadata retrieval process with OAuth2 token...")
        namespace_prefix = processes[process_id].get('namespace_prefix')
        _run_metadata_extraction(process_id, access_token, instance_url, namespace_prefix)
    except Exception as e:
        error_msg = f"An error occurred: {str(e)}"
        logger.exception(f"Error in process {process_id}: {e}")
        add_log(process_id, error_msg)
        processes[process_id]['status'] = STATUS_ERROR
        processes[process_id]['error'] = str(e)
    finally:
        running_flags[process_id] = False


def _run_metadata_extraction(process_id: str, access_token: str, instance_url: str, namespace_prefix: Optional[str] = None) -> None:
    """
    Common metadata extraction logic.
    
    Args:
        process_id: Process identifier
        access_token: Salesforce OAuth2 access token
        instance_url: Salesforce instance URL
        namespace_prefix: Optional namespace prefix to filter objects by app
    """
    from config import STATUS_COMPLETED, STATUS_ERROR, STATUS_TERMINATED
    
    # Retrieve all objects
    objects = salesforce_service.get_all_objects(access_token, instance_url)
    add_log(process_id, f"Retrieved {len(objects)} objects.")
    
    if namespace_prefix and namespace_prefix != 'all':
        # Check if it's a namespace or app ID
        is_namespace = (
            len(namespace_prefix) < 20 and
            not namespace_prefix.startswith('0') and
            '__' not in namespace_prefix
        )
        if is_namespace:
            add_log(process_id, f"Filtering objects by app namespace: {namespace_prefix}")
        else:
            add_log(process_id, f"Selected app (ID: {namespace_prefix[:20]}...) - extracting all objects (app has no namespace)")
    
    # Extract metadata
    def should_continue() -> bool:
        """Check if processing should continue."""
        return running_flags.get(process_id, False)
    
    def log_progress(message: str) -> None:
        """Log progress messages to the UI."""
        add_log(process_id, message)
    
    metadata_rows = salesforce_service.extract_metadata(
        access_token,
        instance_url,
        objects,
        should_continue,
        log_callback=log_progress,
        namespace_prefix=namespace_prefix
    )
    
    if not should_continue():
        add_log(process_id, "Process terminated by user.")
        processes[process_id]['status'] = STATUS_TERMINATED
        return
    
    # Save metadata CSV
    metadata_file_path = file_service.save_metadata_csv(metadata_rows)
    add_log(process_id, f"Metadata saved to {metadata_file_path}")
    
    # Get app name for file naming
    app_name = processes[process_id].get('app_name')
    
    # Generate Lucidchart CSV with app name
    lucid_file_path = file_service.generate_lucid_csv(metadata_file_path, app_name=app_name)
    
    # Store file paths
    processes[process_id]['metadata_file'] = metadata_file_path
    processes[process_id]['lucid_file'] = lucid_file_path
    
    add_log(process_id, "Metadata retrieval completed successfully!")
    processes[process_id]['status'] = STATUS_COMPLETED


# Route handlers
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request) -> HTMLResponse:
    """Render home page."""
    template = templates.get_template("home.html")
    return HTMLResponse(content=template.render(request=request))


@app.get("/features", response_class=HTMLResponse)
async def features_page(request: Request) -> HTMLResponse:
    """Render features page."""
    template = templates.get_template("features.html")
    return HTMLResponse(content=template.render(request=request))


@app.get("/exporter", response_class=HTMLResponse)
async def exporter_page(request: Request) -> HTMLResponse:
    """Render data model exporter page."""
    settings = get_settings()
    template = templates.get_template("exporter.html")
    
    # Environment-specific instance URLs
    env_urls = {
        "DEV": "https://cloudblazer2-dev-ed.develop.my.salesforce.com",
        "STG": "https://test.salesforce.com",
        "PROD": "https://login.salesforce.com"
    }
    
    return HTMLResponse(content=template.render(
        request=request,
        default_instance_url=settings.salesforce_instance_url,
        default_client_id=settings.salesforce_client_id or "",
        default_client_secret=settings.salesforce_client_secret or "",
        env_urls=env_urls,
    ))


@app.get("/lucidchart", response_class=HTMLResponse)
async def lucidchart_page(request: Request) -> HTMLResponse:
    """Render Lucidchart information page."""
    template = templates.get_template("lucidchart.html")
    return HTMLResponse(content=template.render(request=request))


@app.get("/salesforce-redirect-uri")
async def get_salesforce_redirect_uri(request: Request) -> JSONResponse:
    """
    Get the Salesforce redirect URI that needs to be configured.
    This is a helper endpoint to show users exactly what to configure.
    
    Args:
        request: FastAPI request object
        
    Returns:
        JSON response with the redirect URI
    """
    redirect_uri = get_redirect_uri(
        request.base_url,
        settings.salesforce_redirect_uri,
        "/salesforce-callback"
    )
    
    return JSONResponse({
        "redirect_uri": redirect_uri,
        "instructions": {
            "step1": "Go to Salesforce Setup → App Manager → Your Connected App",
            "step2": "Click 'Manage' → 'Edit Policies'",
            "step3": f"Add this exact URL to the 'Callback URL' field: {redirect_uri}",
            "step4": "Click 'Save' and wait 2-10 minutes for changes to take effect",
            "note": "The URL must match exactly, including http:// or https:// and the /salesforce-callback path"
        }
    })


@app.get("/salesforce-auth")
async def salesforce_auth(
    request: Request,
    client_id: str,
    client_secret: str,
    instance_url: str,
    state: Optional[str] = None
) -> JSONResponse:
    """
    Initiate Salesforce OAuth2 authentication (supports MFA).
    
    Args:
        request: FastAPI request object
        client_id: Salesforce Connected App Consumer Key
        client_secret: Salesforce Connected App Consumer Secret
        instance_url: Salesforce instance URL
        state: Optional state parameter for CSRF protection
        
    Returns:
        JSON response with authorization URL
    """
    try:
        # Validate inputs
        client_id = client_id.strip()
        client_secret = client_secret.strip()
        instance_url = instance_url.strip().rstrip('/')
        
        if not all([client_id, client_secret, instance_url]):
            raise HTTPException(status_code=400, detail="Client ID, Client Secret, and Instance URL are required")
        
        if not instance_url.startswith('https://'):
            raise HTTPException(status_code=400, detail="Instance URL must start with https://")
        
        # Generate state if not provided (store client_secret temporarily)
        if not state:
            state = str(uuid.uuid4())
        
        # Get app_namespace from query params if provided
        app_namespace = request.query_params.get('app_namespace')
        
        # Store credentials temporarily in session (using process storage as temporary)
        # In production, use proper session storage or Redis
        temp_storage_key = f"oauth_{state}"
        processes[temp_storage_key] = {
            'client_id': client_id,
            'client_secret': client_secret,
            'instance_url': instance_url,
            'status': 'oauth_pending',
            'app_namespace': app_namespace
        }
        
        redirect_uri = get_redirect_uri(
            request.base_url,
            settings.salesforce_redirect_uri,
            "/salesforce-callback"
        )
        
        logger.info(f"Salesforce OAuth auth requested. Instance: {instance_url}")
        logger.info(f"Redirect URI: {redirect_uri}")
        logger.info(f"IMPORTANT: Make sure this redirect URI is configured in your Salesforce Connected App!")
        # Do not log client_id or client_secret for security reasons
        
        auth_url = salesforce_service.get_auth_url(instance_url, client_id, redirect_uri, state)
        
        return JSONResponse({
            "auth_url": auth_url, 
            "state": state,
            "redirect_uri": redirect_uri  # Include in response for debugging
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating Salesforce OAuth: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to initiate OAuth: {str(e)}")


@app.get("/salesforce-callback")
async def salesforce_callback(
    request: Request,
    background_tasks: BackgroundTasks,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None
) -> HTMLResponse:
    """
    Handle Salesforce OAuth2 callback and start metadata extraction.
    
    Args:
        request: FastAPI request object
        code: Authorization code from OAuth2 callback
        state: State parameter from OAuth2 callback
        error: Error parameter if OAuth failed
        
    Returns:
        HTML response with status
    """
    if error:
        # Provide helpful error messages for common OAuth errors
        error_description = request.query_params.get('error_description', error)
        error_message = error
        help_text = ""
        
        if 'redirect_uri_mismatch' in error.lower():
            error_message = "Redirect URI Mismatch"
            help_text = """
            <div style="margin-top: 20px; padding: 15px; background: #fff3cd; border: 1px solid #ffc107; border-radius: 5px; text-align: left;">
                <h3 style="margin-top: 0;">How to Fix:</h3>
                <ol>
                    <li>Go to Salesforce Setup → External Client Apps → Your External Client App</li>
                    <li>Click "Manager" → "OAuth Settings"</li>
                    <li>In the "OAuth Settings" section, add the following Callback URL:</li>
                    <li style="margin-left: 20px; font-family: monospace; background: #f5f5f5; padding: 5px;">
                        {redirect_uri}
                    </li>
                    <li>Click "Save"</li>
                    <li>Wait 2-10 minutes for changes to take effect</li>
                </ol>
                <p><strong>Note:</strong> For local development, use: <code>http://localhost:8000/salesforce-callback</code></p>
                <p><strong>For Heroku:</strong> Use your Heroku app URL: <code>https://your-app-name.herokuapp.com/salesforce-callback</code></p>
            </div>
            """
            # Try to get the redirect URI that was used
            try:
                # Get from request or reconstruct
                redirect_uri = get_redirect_uri(
                    request.base_url,
                    settings.salesforce_redirect_uri,
                    "/salesforce-callback"
                )
                help_text = help_text.format(redirect_uri=redirect_uri)
            except:
                help_text = help_text.format(redirect_uri="[Check server logs for the exact redirect URI]")
        elif 'code_challenge' in error_description.lower() or 'pkce' in error_description.lower():
            error_message = "PKCE Required"
            help_text = """
            <div style="margin-top: 20px; padding: 15px; background: #fff3cd; border: 1px solid #ffc107; border-radius: 5px; text-align: left;">
                <h3 style="margin-top: 0;">How to Fix: Disable PKCE Requirement</h3>
                <p style="margin-bottom: 10px;"><strong>Your External Client App requires PKCE, but this application doesn't use PKCE.</strong></p>
                <ol>
                    <li>Go to Salesforce Setup → External Client Apps → Your External Client App</li>
                    <li>Click "Manager" → "OAuth Settings" (or "Edit Policies")</li>
                    <li>Find the setting: <strong>"Require PKCE for Authorization Code Flow"</strong></li>
                    <li><strong>Uncheck/Disable</strong> this option</li>
                    <li>Click "Save"</li>
                    <li>Wait 2-10 minutes for changes to take effect</li>
                </ol>
                <p style="margin-top: 10px;"><strong>Alternative:</strong> If you cannot disable PKCE, you'll need to use the Password Flow instead of OAuth2 Flow (if MFA is not enabled).</p>
            </div>
            """
        
        error_html = f"""
        <html>
        <head>
            <title>Authentication Failed</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 40px; max-width: 800px; margin: 0 auto; }}
                .error {{ color: #d32f2f; background: #ffebee; padding: 20px; border-radius: 5px; }}
                code {{ background: #f5f5f5; padding: 2px 6px; border-radius: 3px; }}
            </style>
        </head>
        <body>
            <div class="error">
                <h2>Salesforce Authentication Failed</h2>
                <p><strong>Error:</strong> {error_message}</p>
                <p><strong>Details:</strong> {error_description}</p>
                {help_text}
                <p style="margin-top: 20px;"><a href="/exporter" style="color: #1976d2; text-decoration: none;">← Return to Exporter</a></p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=400)
    
    if not code or not state:
        error_html = """
        <html>
        <head>
            <title>Authentication Failed</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 40px; text-align: center; }}
                .error {{ color: #d32f2f; background: #ffebee; padding: 20px; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="error">
                <h2>Salesforce Authentication Failed</h2>
                <p>Missing authorization code or state parameter.</p>
                <p><a href="/exporter">Return to Exporter</a></p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=400)
    
    try:
        # Retrieve stored credentials
        temp_storage_key = f"oauth_{state}"
        if temp_storage_key not in processes:
            raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
        
        stored_data = processes[temp_storage_key]
        client_id = stored_data['client_id']
        client_secret = stored_data['client_secret']
        instance_url = stored_data['instance_url']
        app_namespace = stored_data.get('app_namespace')
        
        # Clean up temporary storage
        del processes[temp_storage_key]
        
        # Exchange code for token
        redirect_uri = get_redirect_uri(
            request.base_url,
            settings.salesforce_redirect_uri,
            "/salesforce-callback"
        )
        
        token_response = salesforce_service.exchange_code_for_token(
            instance_url, client_id, client_secret, code, redirect_uri
        )
        
        access_token = token_response['access_token']
        instance_url_from_token = token_response.get('instance_url', instance_url)
        
        # Store token temporarily for app loading (using state as key)
        # Create a session ID for app loading
        session_id = str(uuid.uuid4())
        processes[f"oauth_session_{session_id}"] = {
            'access_token': access_token,
            'instance_url': instance_url_from_token,
            'status': 'authenticated',
            'created_at': datetime.now().isoformat()
        }
        
        # Redirect back to exporter page with session_id to load apps
        return RedirectResponse(url=f"/exporter?session_id={session_id}", status_code=303)
    except Exception as e:
        logger.error(f"Error in Salesforce OAuth callback: {e}")
        error_html = f"""
        <html>
        <head>
            <title>Authentication Failed</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 40px; text-align: center; }}
                .error {{ color: #d32f2f; background: #ffebee; padding: 20px; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="error">
                <h2>Salesforce Authentication Failed</h2>
                <p>Error: {str(e)}</p>
                <p><a href="/exporter">Return to Exporter</a></p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=500)


@app.get("/select-app", response_class=HTMLResponse)
async def select_app_page(
    request: Request,
    session_id: Optional[str] = None
) -> HTMLResponse:
    """
    App selection page after OAuth2 authentication.
    
    Args:
        request: FastAPI request object
        session_id: OAuth session ID
        
    Returns:
        HTML response with app selection page
    """
    if not session_id:
        return HTMLResponse(content="<html><body><h2>Error: Missing session ID</h2><p><a href='/exporter'>Return to Exporter</a></p></body></html>", status_code=400)
    
    session_key = f"oauth_session_{session_id}"
    if session_key not in processes:
        return HTMLResponse(content="<html><body><h2>Error: Invalid or expired session</h2><p><a href='/exporter'>Return to Exporter</a></p></body></html>", status_code=400)
    
    template = templates.get_template("select_app.html")
    return HTMLResponse(content=template.render(
        request=request,
        session_id=session_id
    ))


@app.post("/start-extraction")
async def start_extraction(
    request: Request,
    background_tasks: BackgroundTasks,
    session_id: str = Form(...),
    app_namespace: str = Form(...),
    app_name: str = Form("")
) -> JSONResponse:
    """
    Start metadata extraction after app selection.
    
    Args:
        request: FastAPI request object
        background_tasks: Background tasks manager
        session_id: OAuth session ID
        app_namespace: Selected app namespace prefix
        app_name: Selected app name (for file naming)
        
    Returns:
        JSON response with process ID
    """
    session_key = f"oauth_session_{session_id}"
    if session_key not in processes:
        raise HTTPException(status_code=400, detail="Invalid or expired session")
    
    session_data = processes[session_key]
    access_token = session_data['access_token']
    instance_url = session_data['instance_url']
    
    # Create process
    process_id = str(uuid.uuid4())
    process_data = create_process_data()
    
    if app_namespace and app_namespace.strip() and app_namespace != 'all':
        process_data['namespace_prefix'] = app_namespace.strip()
        process_data['app_name'] = app_name.strip() if app_name else app_namespace.strip()
    else:
        process_data['app_name'] = 'AllObjects'
    
    processes[process_id] = process_data
    
    # Clean up session
    del processes[session_key]
    
    # Start background task
    background_tasks.add_task(
        run_process_task_with_token,
        process_id,
        access_token,
        instance_url
    )
    
    return JSONResponse({"process_id": process_id, "status": "started"})


@app.post("/start")
async def start_process(
    request: Request,
    background_tasks: BackgroundTasks,
    client_id: str = Form(...),
    client_secret: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    instance_url: str = Form(...),
    app_namespace: Optional[str] = Form(None)
) -> JSONResponse:
    """
    Start the metadata extraction process.
    
    Args:
        request: FastAPI request object
        background_tasks: Background tasks manager
        client_id: Salesforce client ID
        client_secret: Salesforce client secret
        username: Salesforce username
        password: Salesforce password
        instance_url: Salesforce instance URL
        
    Returns:
        JSON response with process ID and status
    """
    # Validate and normalize inputs
    client_id = client_id.strip()
    client_secret = client_secret.strip()
    username = username.strip()
    password = password.strip()
    instance_url = instance_url.strip().rstrip('/')  # Remove trailing slash
    
    # Basic validation
    if not all([client_id, client_secret, username, password, instance_url]):
        raise HTTPException(status_code=400, detail="All fields are required")
    
    if not instance_url.startswith('https://'):
        raise HTTPException(status_code=400, detail="Instance URL must start with https://")
    
    logger.info(f"Starting process for user: {username}")
    logger.info(f"Instance URL: {instance_url}")
    # Do not log client_id or client_secret for security reasons
    
    process_id = str(uuid.uuid4())
    process_data = create_process_data()
    if app_namespace and app_namespace.strip() and app_namespace != 'all':
        process_data['namespace_prefix'] = app_namespace.strip()
        # Get app_name from form if provided, otherwise use namespace
        app_name = request.form.get('app_name', app_namespace.strip())
        process_data['app_name'] = app_name
    else:
        process_data['app_name'] = 'AllObjects'
    processes[process_id] = process_data
    
    credentials: SalesforceCredentials = {
        'client_id': client_id,
        'client_secret': client_secret,
        'username': username,
        'password': password,
        'instance_url': instance_url
    }
    
    # Start background task
    background_tasks.add_task(run_process_task, process_id, credentials)
    
    return JSONResponse({"process_id": process_id, "status": "started"})


@app.post("/terminate/{process_id}")
async def terminate_process(process_id: str) -> JSONResponse:
    """
    Terminate a running process.
    
    Args:
        process_id: Process identifier
        
    Returns:
        JSON response with termination status
    """
    from config import STATUS_TERMINATING
    
    if process_id not in running_flags:
        raise HTTPException(status_code=404, detail="Process not found")
    
    running_flags[process_id] = False
    add_log(process_id, "Terminate request received.")
    processes[process_id]['status'] = STATUS_TERMINATING
    
    return JSONResponse({"status": "terminated"})


@app.post("/authenticate-for-apps")
async def authenticate_for_apps(
    credentials: dict = Body(...)
) -> JSONResponse:
    """
    Authenticate with Salesforce to get access token for loading apps (Password Flow).
    
    Args:
        request: FastAPI request object
        credentials: Salesforce credentials (client_id, client_secret, username, password, instance_url)
        
    Returns:
        JSON response with access_token and instance_url
    """
    try:
        from models import SalesforceCredentials
        
        # Validate credentials
        client_id = credentials.get('client_id', '').strip()
        client_secret = credentials.get('client_secret', '').strip()
        username = credentials.get('username', '').strip()
        password = credentials.get('password', '').strip()
        instance_url = credentials.get('instance_url', '').strip().rstrip('/')
        
        if not all([client_id, client_secret, username, password, instance_url]):
            raise HTTPException(status_code=400, detail="All credentials are required")
        
        if not instance_url.startswith('https://'):
            raise HTTPException(status_code=400, detail="Instance URL must start with https://")
        
        # Create credentials object
        sf_credentials: SalesforceCredentials = {
            'client_id': client_id,
            'client_secret': client_secret,
            'username': username,
            'password': password,
            'instance_url': instance_url
        }
        
        # Get access token
        token_response = salesforce_service.get_access_token(sf_credentials)
        access_token = token_response['access_token']
        instance_url_from_token = token_response.get('instance_url', instance_url)
        
        return JSONResponse({
            "access_token": access_token,
            "instance_url": instance_url_from_token
        })
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Error authenticating for apps: {e}")
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")


@app.get("/salesforce-apps")
async def get_salesforce_apps(
    request: Request,
    session_id: Optional[str] = None,
    access_token: Optional[str] = None,
    instance_url: Optional[str] = None
) -> JSONResponse:
    """
    Get list of installed Salesforce apps/packages.
    
    Args:
        request: FastAPI request object
        session_id: OAuth session ID (alternative to access_token/instance_url)
        access_token: Salesforce OAuth access token (query parameter)
        instance_url: Salesforce instance URL (query parameter)
        
    Returns:
        JSON response with list of apps
    """
    try:
        # If session_id provided, get token from session
        if session_id:
            session_key = f"oauth_session_{session_id}"
            if session_key not in processes:
                raise HTTPException(status_code=400, detail="Invalid or expired session")
            session_data = processes[session_key]
            access_token = session_data['access_token']
            instance_url = session_data['instance_url']
        else:
            # Get from query params if not provided as function args
            if not access_token:
                access_token = request.query_params.get('access_token')
            if not instance_url:
                instance_url = request.query_params.get('instance_url')
        
        if not access_token or not instance_url:
            raise HTTPException(status_code=400, detail="access_token and instance_url are required")
        
        apps = salesforce_service.get_installed_apps(access_token, instance_url)
        return JSONResponse({"apps": apps})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching Salesforce apps: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch apps: {str(e)}")


@app.get("/status/{process_id}")
async def get_status(process_id: str) -> JSONResponse:
    """
    Get the status and logs of a process.
    
    Args:
        process_id: Process identifier
        
    Returns:
        JSON response with process status and data
    """
    if process_id not in processes:
        raise HTTPException(status_code=404, detail="Process not found")
    
    process_data = processes[process_id].copy()
    
    # Include file information if available
    if 'metadata_file' in process_data and process_data['metadata_file']:
        process_data['has_metadata_file'] = True
        process_data['metadata_filename'] = os.path.basename(process_data['metadata_file'])
    
    if 'lucid_file' in process_data and process_data['lucid_file']:
        process_data['has_lucid_file'] = True
        process_data['lucid_filename'] = os.path.basename(process_data['lucid_file'])
    
    return JSONResponse(process_data)


@app.get("/download/{process_id}/{file_type}")
async def download_file(process_id: str, file_type: str) -> FileResponse:
    """
    Download the generated CSV files.
    
    Args:
        process_id: Process identifier
        file_type: Type of file to download (metadata or lucid)
        
    Returns:
        File response with the CSV file
        
    Raises:
        HTTPException: If process or file not found, or invalid file type
    """
    if process_id not in processes:
        raise HTTPException(status_code=404, detail="Process not found")
    
    if not validate_file_type(file_type):
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    process_data = processes[process_id]
    
    if file_type == FILE_TYPE_METADATA:
        file_path = process_data.get('metadata_file')
        filename = "salesforce_metadata.csv"
    else:  # FILE_TYPE_LUCID
        file_path = process_data.get('lucid_file')
        filename = os.path.basename(file_path) if file_path else "salesforce_metadata_lucid.csv"
    
    if not file_path or not file_service.file_exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='text/csv'
    )


@app.get("/google-drive-auth")
async def google_drive_auth(request: Request) -> JSONResponse:
    """
    Initiate Google Drive OAuth2 authentication.
    
    Args:
        request: FastAPI request object
        
    Returns:
        JSON response with authorization URL
        
    Raises:
        HTTPException: If Google Drive is not configured
    """
    try:
        redirect_uri = get_redirect_uri(
            request.base_url,
            settings.google_redirect_uri
        )
        logger.info(f"Google Drive auth requested. Redirect URI: {redirect_uri}")
        auth_url = google_drive_service.get_auth_url(redirect_uri)
        logger.info(f"Generated Google Drive auth URL: {auth_url}")
        return JSONResponse({"auth_url": auth_url})
    except GoogleDriveAuthError as e:
        logger.error(f"Google Drive auth error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "detail": "Google Drive integration not configured. Please set GOOGLE_CLIENT_ID environment variable."}
        )
    except Exception as e:
        logger.error(f"Unexpected error in Google Drive auth: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "detail": "An unexpected error occurred while initiating Google Drive authentication."}
        )


@app.get("/google-drive-callback")
async def google_drive_callback(
    request: Request,
    code: Optional[str] = None,
    error: Optional[str] = None
) -> HTMLResponse:
    """
    Handle Google Drive OAuth2 callback.
    
    Args:
        request: FastAPI request object
        code: Authorization code from OAuth2 callback
        error: Error message if authentication failed
        
    Returns:
        HTML response with authentication result
    """
    if error:
        return HTMLResponse(
            content=f"<html><body><h1>Authentication Error</h1><p>{error}</p>"
                    f"<script>window.close();</script></body></html>"
        )
    
    if not code:
        return HTMLResponse(
            content="<html><body><h1>No authorization code received</h1>"
                   "<script>window.close();</script></body></html>"
        )
    
    try:
        redirect_uri = get_redirect_uri(
            request.base_url,
            settings.google_redirect_uri
        )
        tokens = google_drive_service.exchange_code_for_token(code, redirect_uri)
        access_token = tokens.get("access_token")
        
        return HTMLResponse(content=f"""
        <html>
        <body>
            <h1>Authentication Successful!</h1>
            <p>You can now close this window and return to the application.</p>
            <p>Use the upload button again to upload your file.</p>
            <script>
                sessionStorage.setItem('google_drive_token', '{access_token}');
                setTimeout(() => window.close(), 2000);
            </script>
        </body>
        </html>
        """)
    except GoogleDriveAuthError as e:
        logger.error(f"Token exchange error: {e}")
        return HTMLResponse(
            content=f"<html><body><h1>Error</h1><p>Failed to authenticate: {str(e)}</p>"
                   "<script>window.close();</script></body></html>"
        )


@app.post("/upload-to-drive/{process_id}")
async def upload_to_drive(process_id: str, request: Request) -> JSONResponse:
    """
    Upload file to Google Drive after OAuth2 authentication.
    
    Args:
        process_id: Process identifier
        request: FastAPI request object
        
    Returns:
        JSON response with upload result
        
    Raises:
        HTTPException: If process not found, file not found, or upload fails
    """
    if process_id not in processes:
        raise HTTPException(status_code=404, detail="Process not found")
    
    process_data = processes[process_id]
    file_path = process_data.get('lucid_file')
    
    if not file_path or not file_service.file_exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Get access token from request body
    try:
        body = await request.json()
    except Exception:
        body = {}
    
    access_token = body.get("access_token")
    
    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="No access token provided. Please authenticate first."
        )
    
    try:
        result = google_drive_service.upload_file(file_path, access_token)
        return JSONResponse({
            "success": True,
            "file_id": result['file_id'],
            "web_view_link": result['web_view_link'],
            "message": "File uploaded successfully to Google Drive!"
        })
    except GoogleDriveUploadError as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/lucidchart-auth")
async def lucidchart_auth(request: Request, state: Optional[str] = None) -> JSONResponse:
    """
    Initiate Lucidchart OAuth2 authentication.
    
    Args:
        request: FastAPI request object
        state: Optional state parameter for CSRF protection
        
    Returns:
        JSON response with authorization URL
        
    Raises:
        HTTPException: If Lucidchart is not configured
    """
    try:
        redirect_uri = get_redirect_uri(
            request.base_url,
            settings.lucidchart_redirect_uri
        )
        auth_url = lucidchart_service.get_auth_url(redirect_uri, state)
        return JSONResponse({"auth_url": auth_url})
    except LucidchartAuthError as e:
        logger.error(f"Lucidchart auth error: {e}")
        # Return a user-friendly error message instead of raising HTTPException
        return JSONResponse(
            status_code=200,  # Return 200 so frontend can handle it gracefully
            content={
                "error": str(e),
                "detail": "Lucidchart integration is not configured. Please set LUCIDCHART_CLIENT_ID and LUCIDCHART_CLIENT_SECRET environment variables. See README.md for setup instructions."
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error in Lucidchart auth: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={
                "error": str(e),
                "detail": "An unexpected error occurred while initiating Lucidchart authentication."
            }
        )


@app.get("/lucidchart-callback")
async def lucidchart_callback(
    request: Request,
    code: Optional[str] = None,
    error: Optional[str] = None,
    state: Optional[str] = None
) -> HTMLResponse:
    """
    Handle Lucidchart OAuth2 callback.
    
    Args:
        request: FastAPI request object
        code: Authorization code from OAuth2 callback
        error: Error message if authentication failed
        state: State parameter from OAuth2 callback
        
    Returns:
        HTML response with authentication result
    """
    if error:
        logger.error(f"Lucidchart OAuth error: {error}")
        return HTMLResponse(
            content=f"""<html>
            <head><title>Authentication Error</title></head>
            <body style="font-family: Arial, sans-serif; padding: 20px; text-align: center;">
                <h1 style="color: #d32f2f;">Authentication Error</h1>
                <p>{error}</p>
                <p>You can close this window and try again.</p>
                <script>
                    try {{
                        // Try to notify parent window
                        if (window.opener) {{
                            window.opener.postMessage({{type: 'lucidchart_auth_error', error: '{error}'}}, '*');
                        }}
                    }} catch (e) {{
                        console.error('Error notifying parent:', e);
                    }}
                    setTimeout(() => window.close(), 3000);
                </script>
            </body>
            </html>"""
        )
    
    if not code:
        logger.error("No authorization code received in Lucidchart callback")
        return HTMLResponse(
            content="""<html>
            <head><title>No Authorization Code</title></head>
            <body style="font-family: Arial, sans-serif; padding: 20px; text-align: center;">
                <h1 style="color: #d32f2f;">No authorization code received</h1>
                <p>Please try again.</p>
                <script>
                    try {{
                        if (window.opener) {{
                            window.opener.postMessage({{type: 'lucidchart_auth_error', error: 'No authorization code received'}}, '*');
                        }}
                    }} catch (e) {{
                        console.error('Error notifying parent:', e);
                    }}
                    setTimeout(() => window.close(), 3000);
                </script>
            </body>
            </html>"""
        )
    
    try:
        redirect_uri = get_redirect_uri(
            request.base_url,
            settings.lucidchart_redirect_uri
        )
        tokens = lucidchart_service.exchange_code_for_token(code, redirect_uri)
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token", "")
        
        if not access_token:
            raise LucidchartAuthError("No access token received from Lucidchart")
        
        # Escape tokens for JavaScript to prevent XSS
        access_token_escaped = access_token.replace("'", "\\'").replace('"', '\\"')
        refresh_token_escaped = refresh_token.replace("'", "\\'").replace('"', '\\"') if refresh_token else ""
        
        logger.info("Lucidchart authentication successful")
        
        return HTMLResponse(content=f"""<html>
        <head>
            <title>Authentication Successful</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    padding: 20px;
                    text-align: center;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    min-height: 100vh;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                }}
                .success-box {{
                    background: white;
                    color: #333;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    max-width: 400px;
                }}
                h1 {{
                    color: #28a745;
                    margin-bottom: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="success-box">
                <h1>✓ Authentication Successful!</h1>
                <p>You can now close this window and return to the application.</p>
                <p style="font-size: 14px; color: #666; margin-top: 20px;">This window will close automatically...</p>
            </div>
            <script>
                try {{
                    // Store token in sessionStorage
                    sessionStorage.setItem('lucidchart_token', '{access_token_escaped}');
                    {f"sessionStorage.setItem('lucidchart_refresh_token', '{refresh_token_escaped}');" if refresh_token_escaped else ""}
                    
                    // Notify parent window
                    if (window.opener) {{
                        window.opener.postMessage({{type: 'lucidchart_auth_success', token: '{access_token_escaped}'}}, '*');
                    }}
                    
                    // Reload parent window to update UI
                    if (window.opener && !window.opener.closed) {{
                        window.opener.location.reload();
                    }}
                }} catch (e) {{
                    console.error('Error storing token:', e);
                }}
                
                setTimeout(() => {{
                    window.close();
                }}, 2000);
            </script>
        </body>
        </html>""")
    except LucidchartAuthError as e:
        logger.error(f"Token exchange error: {e}")
        error_msg = str(e).replace("'", "\\'").replace('"', '\\"')
        return HTMLResponse(
            content=f"""<html>
            <head><title>Authentication Error</title></head>
            <body style="font-family: Arial, sans-serif; padding: 20px; text-align: center;">
                <h1 style="color: #d32f2f;">Authentication Failed</h1>
                <p>{error_msg}</p>
                <p>Please try again.</p>
                <script>
                    try {{
                        if (window.opener) {{
                            window.opener.postMessage({{type: 'lucidchart_auth_error', error: '{error_msg}'}}, '*');
                        }}
                    }} catch (e) {{
                        console.error('Error notifying parent:', e);
                    }}
                    setTimeout(() => window.close(), 3000);
                </script>
            </body>
            </html>"""
        )
    except Exception as e:
        logger.error(f"Unexpected error in Lucidchart callback: {e}", exc_info=True)
        error_msg = "An unexpected error occurred. Please try again."
        return HTMLResponse(
            content=f"""<html>
            <head><title>Error</title></head>
            <body style="font-family: Arial, sans-serif; padding: 20px; text-align: center;">
                <h1 style="color: #d32f2f;">Error</h1>
                <p>{error_msg}</p>
                <script>
                    setTimeout(() => window.close(), 3000);
                </script>
            </body>
            </html>"""
        )


@app.get("/lucidchart-documents")
async def get_lucidchart_documents(request: Request) -> JSONResponse:
    """
    Get list of user's Lucidchart documents.
    
    Args:
        request: FastAPI request object
        
    Returns:
        JSON response with list of documents
        
    Raises:
        HTTPException: If authentication fails or API error occurs
    """
    # Get access token from request header or query parameter
    access_token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not access_token:
        # Try to get from query parameter (for frontend use)
        access_token = request.query_params.get("token")
    
    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="No access token provided. Please authenticate first."
        )
    
    try:
        documents = lucidchart_service.get_documents(access_token)
        # Add embed URLs to each document
        for doc in documents:
            doc_id = doc.get('id')
            if doc_id:
                doc['embed_url'] = lucidchart_service.get_document_embed_url(doc_id, access_token)
        return JSONResponse({"documents": documents})
    except LucidchartAPIError as e:
        logger.error(f"Error getting documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/lucidchart-import/{process_id}")
async def import_to_lucidchart(process_id: str, request: Request) -> JSONResponse:
    """
    Import CSV file to Lucidchart.
    
    Args:
        process_id: Process identifier
        request: FastAPI request object
        
    Returns:
        JSON response with import result
        
    Raises:
        HTTPException: If process not found, file not found, or import fails
    """
    if process_id not in processes:
        raise HTTPException(status_code=404, detail="Process not found")
    
    process_data = processes[process_id]
    file_path = process_data.get('lucid_file')
    
    if not file_path or not file_service.file_exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Get access token and document name from request body
    try:
        body = await request.json()
    except Exception:
        body = {}
    
    access_token = body.get("access_token")
    document_name = body.get("document_name", "Salesforce Data Model")
    
    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="No access token provided. Please authenticate first."
        )
    
    try:
        # Read CSV file
        with open(file_path, 'r', encoding='utf-8') as f:
            csv_content = f.read()
        
        # Create document in Lucidchart
        result = lucidchart_service.create_document_from_csv(
            csv_content,
            document_name,
            access_token
        )
        
        return JSONResponse({
            "success": True,
            "document_id": result['document_id'],
            "embed_url": result['embed_url'],
            "message": result.get('message', 'Document created successfully!')
        })
    except LucidchartAPIError as e:
        logger.error(f"Import error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    
    # Use PORT from environment (Heroku provides this) or default from settings
    port = int(os.getenv("PORT", settings.port))
    uvicorn.run(app, host=settings.host, port=port)
