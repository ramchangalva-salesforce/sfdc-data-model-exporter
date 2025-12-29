# Salesforce Data Model Exporter

A lightweight FastAPI-based web application that extracts data models from Salesforce orgs and exports them to CSV format. The exported CSV files are compatible with Lucidchart for ERD visualization.

## Features

- **Dual Authentication Methods**:
  - **Password Flow**: Direct username/password authentication (no MFA support)
  - **OAuth2 Flow**: Full OAuth2 Authorization Code Flow with MFA support
  
- **Environment Management**:
  - Environment dropdown (DEV, STG, PROD) for easy instance URL selection
  - Automatic instance URL updates based on environment selection
  - Visual display of current instance URL

- **App-Specific Data Model Extraction**:
  - Fetches all Salesforce apps from App Launcher
  - Filter metadata extraction by selected app namespace
  - App name included in generated filenames for easy identification

- **Real-time Processing**:
  - Background task processing with real-time log updates
  - Process termination capability
  - Status polling and progress tracking

- **Export Capabilities**:
  - Export data models to CSV format
  - Generate Lucidchart-compatible CSV files for ERD import
  - App-specific filenames (e.g., `2025_12_29_AppName_salesforce_metadata_lucid.csv`)

- **Integration Options**:
  - Download exported files directly
  - Upload files to Google Drive (OAuth2 authentication with personal Google accounts)
  - Lucidchart login and chart viewing
  - Import ERD directly to Lucidchart from desktop or Google Drive

- **Session Management**:
  - Sign Out functionality for both authentication flows
  - Session clearing and form reset
  - Secure session handling

## Requirements

- Python 3.11 or higher
- Required packages listed in `requirements.txt`

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd sfdc-data-model-exporter
```

2. Install the required packages:
```bash
pip install -r requirements.txt
```

## Usage

### Starting the Application

1. Start the FastAPI server:
```bash
python main.py
```

Or using uvicorn directly:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

2. Open your web browser and navigate to:
```
http://localhost:8000
```

### Using the Application

#### Step 1: Select Authentication Method

Choose between two authentication methods:

- **Password Flow (No MFA)**: 
  - Use if you don't have MFA enabled
  - Requires appending security token to password
  - Faster setup, no redirects

- **OAuth2 Flow (Supports MFA)**:
  - Use if you have MFA enabled
  - Full OAuth2 flow with redirect to Salesforce login
  - Supports MFA verification codes

#### Step 2: Enter Credentials

**Required Fields:**
- **Client ID (Consumer Key)**: From Salesforce External Client App
- **Client Secret (Consumer Secret)**: From Salesforce External Client App
- **Instance URL**: Your Salesforce instance URL (auto-updated based on Environment selection)

**For Password Flow:**
- **Username**: Your Salesforce username
- **Password + Security Token**: Append security token to password with no space (e.g., `mypass123ABC123`)

**For OAuth2 Flow:**
- No username/password needed in form
- Authentication happens on Salesforce login page

#### Step 3: Select Environment

Choose your environment from the dropdown:
- **DEV**: Development environment (default: `https://cloudblazer2-dev-ed.develop.my.salesforce.com`)
- **STG**: Staging environment (default: `https://test.salesforce.com`)
- **PROD**: Production environment (default: `https://login.salesforce.com`)

The Instance URL field will automatically update based on your selection.

#### Step 4: Authenticate and Load Apps

**Password Flow:**
1. Click **"Login & Load Apps"** button
2. Wait for authentication and app loading
3. Apps will appear in the dropdown

**OAuth2 Flow:**
1. Click **"Login & Load Apps"** button
2. You'll be redirected to Salesforce login page
3. Enter your credentials and MFA code (if required)
4. You'll be redirected back to the exporter page
5. Apps will be automatically loaded

#### Step 5: Select App (Optional)

- Select an app from the dropdown to filter objects by that app's namespace
- Select "All Objects (No Filter)" to extract all objects
- The selected app name will be included in the generated filename

#### Step 6: Start Extraction

- Click **"Retrieve Selected App Data Model"** button
- Monitor progress in the log output
- The extraction runs in the background
- You can terminate the process if needed

#### Step 7: Download or Upload Files

After extraction completes:
- **Download Metadata CSV**: Raw metadata file
- **Download Lucidchart CSV**: Lucidchart-compatible ERD file
- **Upload to Google Drive**: Upload files to your Google Drive (requires Google OAuth)

#### Step 8: Sign Out (Optional)

- Click **"Sign Out"** button to clear your session
- This will reset the form and clear all authentication data
- Useful when switching between different Salesforce orgs or users

## API Endpoints

### Page Routes
- `GET /` - Home page
- `GET /features` - Features page
- `GET /exporter` - Data model exporter page
- `GET /lucidchart` - Lucidchart and ERD information page
- `GET /select-app` - App selection page (OAuth2 flow)

### Authentication Endpoints
- `GET /salesforce-auth` - Initiate Salesforce OAuth2 authentication
- `GET /salesforce-callback` - Handle Salesforce OAuth2 callback
- `GET /salesforce-redirect-uri` - Get the required Salesforce OAuth2 redirect URI
- `POST /authenticate-for-apps` - Authenticate for app loading (Password Flow)

### Process Management
- `POST /start` - Start metadata extraction process (Password Flow)
- `POST /start-extraction` - Start metadata extraction after app selection (OAuth2 Flow)
- `GET /status/{process_id}` - Get process status and logs
- `POST /terminate/{process_id}` - Terminate a running process

### App Management
- `GET /salesforce-apps` - Get list of installed Salesforce apps
  - Query params: `session_id` (OAuth2) or `access_token` + `instance_url` (Password Flow)

### File Operations
- `GET /download/{process_id}/{file_type}` - Download generated CSV files
  - `file_type`: `metadata` or `lucid`

### Google Drive Integration
- `GET /google-drive-auth` - Initiate Google Drive OAuth2 authentication
- `GET /google-drive-callback` - Handle Google Drive OAuth2 callback
- `POST /upload-to-drive/{process_id}` - Upload file to Google Drive

### Lucidchart Integration
- `GET /lucidchart-auth` - Initiate Lucidchart OAuth2 authentication (deprecated - now uses direct links)
- `GET /lucidchart-callback` - Handle Lucidchart OAuth2 callback (deprecated)
- `GET /lucidchart-documents` - Get list of user's Lucidchart documents (deprecated)
- `POST /lucidchart-import/{process_id}` - Import CSV file to Lucidchart (deprecated)

**Note**: Lucidchart integration now uses direct links to Lucidchart login and document pages instead of OAuth2 API integration.

## Output Files

The application generates two CSV files:

1. **Metadata CSV** (`input/YYYY_MM_DD_salesforce_metadata.csv`):
   - Contains all object and field metadata
   - Includes object name, field name, field type, and other metadata

2. **Lucidchart CSV** (`output/YYYY_MM_DD_{AppName}_salesforce_metadata_lucid.csv`):
   - Lucidchart-compatible ERD format
   - Includes table definitions, relationships, and field details
   - App name included in filename if app was selected

## Project Structure

```
sfdc-data-model-exporter/
├── main.py                      # FastAPI application entry point
├── config.py                    # Configuration settings and environment variables
├── models.py                    # Data models and type definitions
├── exceptions.py                # Custom exception classes
├── utils.py                     # Utility functions
├── requirements.txt             # Python dependencies
├── runtime.txt                  # Python version for Heroku
├── Procfile                     # Heroku process file
├── .slugignore                  # Files to exclude from Heroku slug
├── services/
│   ├── __init__.py
│   ├── salesforce_service.py   # Salesforce API integration
│   ├── file_service.py          # File operations (CSV generation)
│   ├── google_drive_service.py   # Google Drive API integration
│   └── lucidchart_service.py    # Lucidchart API integration (simplified)
├── templates/
│   ├── base.html                # Base template with navigation
│   ├── home.html                # Home page
│   ├── features.html            # Features page
│   ├── exporter.html            # Main exporter page
│   ├── lucidchart.html          # Lucidchart integration page
│   └── select_app.html          # App selection page (OAuth2 flow)
├── static/                      # Static files (CSS, JS, images)
├── input/                       # Generated metadata CSV (created automatically)
└── output/                      # Generated Lucidchart CSV (created automatically)
```

## Configuration

### Environment Variables

The application uses environment variables for configuration. Set these before running:

#### Application Settings
- `APP_NAME`: Application name (default: "Salesforce Data Model Exporter")
- `DEBUG`: Enable debug mode (default: "False")
- `LOG_LEVEL`: Logging level (default: "INFO")
- `HOST`: Server host (default: "0.0.0.0")
- `PORT`: Server port (default: "8000")

#### Salesforce Settings
- `SALESFORCE_API_VERSION`: Salesforce API version (default: "v53.0")
- `SALESFORCE_CLIENT_ID`: Salesforce External Client App Consumer Key (optional, pre-fills form)
- `SALESFORCE_CLIENT_SECRET`: Salesforce External Client App Consumer Secret (optional, pre-fills form)
- `SALESFORCE_INSTANCE_URL`: Default Salesforce instance URL (optional)
- `SALESFORCE_REDIRECT_URI`: OAuth2 redirect URI (optional, auto-detected)
- `DEPLOYMENT_ENV`: Deployment environment - DEV, STG, or PROD (default: "DEV")

#### Google Drive Settings (Optional)
- `GOOGLE_CLIENT_ID`: Google OAuth2 Client ID
- `GOOGLE_CLIENT_SECRET`: Google OAuth2 Client Secret
- `GOOGLE_REDIRECT_URI`: Google OAuth2 redirect URI (auto-detected if not set)

#### File Storage Settings
- `INPUT_DIR`: Directory for metadata CSV files (default: "input")
- `OUTPUT_DIR`: Directory for Lucidchart CSV files (default: "output")
- `MAX_LOG_ENTRIES`: Maximum log entries per process (default: 1000)

### Setting Environment Variables

**For Local Development (Linux/Mac):**
```bash
export SALESFORCE_CLIENT_ID="your-consumer-key"
export SALESFORCE_CLIENT_SECRET="your-consumer-secret"
export DEPLOYMENT_ENV="DEV"
```

**For Windows (PowerShell):**
```powershell
$env:SALESFORCE_CLIENT_ID="your-consumer-key"
$env:SALESFORCE_CLIENT_SECRET="your-consumer-secret"
$env:DEPLOYMENT_ENV="DEV"
```

**For Windows (Command Prompt):**
```cmd
set SALESFORCE_CLIENT_ID=your-consumer-key
set SALESFORCE_CLIENT_SECRET=your-consumer-secret
set DEPLOYMENT_ENV=DEV
```

## Salesforce External Client App Setup

To use this application, you need to create an External Client App in Salesforce. This provides the Client ID and Client Secret required for OAuth2 authentication.

### Step-by-Step Instructions:

1. **Log in to Salesforce:**
   - Navigate to your Salesforce org
   - Log in with an administrator account

2. **Navigate to Setup:**
   - Click the gear icon (⚙️) in the top right corner
   - Select **Setup**

3. **Go to External Client Apps:**
   - In the Quick Find box, type "External Client Apps"
   - Click **External Client Apps** under **Apps**

4. **Create New External Client App:**
   - Click **New External Client App** button (top right)
   - Fill in the required information:

   **Basic Information:**
   - **External Client App Name**: `Salesforce Data Model Exporter` (or any name you prefer)
   - **API Name**: Auto-generated
   - **Contact Email**: Your email address
   - **Description**: (Optional) "Application for exporting Salesforce data model to CSV"

5. **Enable OAuth Settings:**
   - Check the box **Enable OAuth Settings**
   - **Callback URL**: **REQUIRED for OAuth2 Flow (MFA support)**. Add the following URLs:
     - For local development: `http://localhost:8000/salesforce-callback`
     - For Heroku: `https://your-app-name.herokuapp.com/salesforce-callback`
     - **Important**: The callback URL must end with `/salesforce-callback` exactly
     - You can add multiple callback URLs (one per line) if deploying to multiple environments
   - **Selected OAuth Scopes**: Add the following scopes:
     - ✅ **Access and manage your data (api)**
     - ✅ **Perform requests on your behalf at any time (refresh_token, offline_access)**
     - ✅ **Access your basic information (id, profile, email, address, phone)**

6. **Configure API Settings:**
   - **Require Secret for Web Server Flow**: ✅ Checked (recommended)
   - **Require Secret for Refresh Token Flow**: ✅ Checked (recommended)
   - **Require PKCE for Authorization Code Flow**: ❌ **Unchecked** (CRITICAL: This application does not use PKCE. If this is checked, you'll get "missing required code challenge" error)

7. **Save the External Client App:**
   - Click **Save**
   - Wait 2-10 minutes for Salesforce to activate the External Client App

8. **Get Your Credentials:**
   - After saving, you'll be redirected to the External Client App detail page
   - Click **Manager** → **OAuth Settings**
   - You'll see:
     - **Consumer Key** (this is your **Client ID**)
     - **Consumer Secret** (this is your **Client Secret**)
     - Click **Reveal** to show the Consumer Secret
   - **Copy both values** - you'll need them for the application

9. **Configure IP Relaxation (Optional but Recommended):**
   - In the External Client App settings, find **IP Relaxation** section
   - Select **Relax IP restrictions** (for development/testing)
   - Or **Enforce IP restrictions** and add your IP addresses (for production)

10. **Configure Permitted Users:**
    - **Permitted Users**: Choose one:
      - **Admin approved users are pre-authorized** (recommended for org-wide access)
      - **All users may self-authorize** (for testing)
    - If using "Admin approved users", go to **Manage** → **Manage Permitted Users** and add users

### Troubleshooting OAuth2 Redirect URI Mismatch:

If you see the error `redirect_uri_mismatch`, follow these steps:

1. **Check the exact redirect URI being used:**
   - Look at the server logs when initiating OAuth - it will show the redirect URI
   - Or visit `/salesforce-redirect-uri` endpoint to see the required redirect URI
   - Or check the error page - it will display the required redirect URI

2. **Update Salesforce External Client App:**
   - Go to Setup → External Client Apps → Your External Client App
   - Click **Manager** → **OAuth Settings**
   - In the **Callback URL** field, add the exact URL shown in the error/logs
   - The URL should be in the format: `http://localhost:8000/salesforce-callback` (local) or `https://your-app.herokuapp.com/salesforce-callback` (Heroku)
   - **Important**: The URL must end with `/salesforce-callback` exactly

3. **Save and wait:**
   - Click **Save**
   - Wait 2-10 minutes for Salesforce to propagate the changes

4. **Verify:**
   - Try the OAuth flow again
   - The redirect URI in the error message should now match what's configured

### Security Token for Password Flow

**Important**: For Password Flow, you must append your security token to your password:

- **Format**: `yourpassword` + `yoursecuritytoken` (no space between them)
- **Example**: If password is `mypass123` and token is `ABC123`, enter: `mypass123ABC123`
- **Get your security token**: 
  - Go to **Setup → My Personal Information → Reset My Security Token**
  - Check your email for the security token
  - The security token is sent to your email address when you reset it

## Authentication Flows

### Password Flow (No MFA)

**Use when:**
- MFA is not enabled on your Salesforce account
- You can append security token to password
- You want faster authentication without redirects

**Steps:**
1. Select "Password Flow (No MFA)" radio button
2. Enter Client ID, Client Secret, Username, Password + Security Token, and Instance URL
3. Click **"Login & Load Apps"** button
4. Apps are loaded automatically after authentication
5. Select an app from the dropdown
6. Click **"Retrieve Selected App Data Model"** to start extraction

### OAuth2 Flow (Supports MFA)

**Use when:**
- MFA is enabled on your Salesforce account
- You want more secure authentication
- You need to enter MFA verification codes

**Steps:**
1. Select "OAuth2 Flow (Supports MFA)" radio button
2. Enter Client ID, Client Secret, and Instance URL
3. Ensure callback URL is configured in Salesforce External Client App
4. Click **"Login & Load Apps"** button
5. You'll be redirected to Salesforce login page
6. Enter your username, password, and MFA code (if required)
7. You'll be redirected back to the exporter page
8. Apps are automatically loaded
9. Select an app from the dropdown
10. Click **"Retrieve Selected App Data Model"** to start extraction

**Important Notes:**
- The callback URL must be configured in Salesforce External Client App before using OAuth2 Flow
- The callback URL is displayed on the exporter page when OAuth2 Flow is selected
- MFA verification code is entered on the Salesforce login page, not in the application form
- After successful authentication, you remain on the same page (no separate app selection page)

## App-Specific Data Model Extraction

The application can filter metadata extraction by Salesforce app:

1. **App Loading:**
   - After authentication, all apps from Salesforce App Launcher are loaded
   - Apps are displayed in a dropdown menu
   - Includes standard Salesforce apps and custom apps

2. **App Selection:**
   - Select an app to filter objects by that app's namespace
   - Select "All Objects (No Filter)" to extract all objects
   - Apps without namespace will extract all objects (standard Salesforce apps)

3. **Filename Generation:**
   - If an app is selected, the app name is included in the filename
   - Format: `YYYY_MM_DD_{AppName}_salesforce_metadata_lucid.csv`
   - Example: `2025_12_29_Sales_salesforce_metadata_lucid.csv`

4. **Namespace Filtering:**
   - Apps with namespace prefix filter objects starting with `{namespace}__`
   - Apps without namespace extract all objects (standard objects)

## Environment Management

The application includes an Environment dropdown for easy instance URL management:

1. **Environment Options:**
   - **DEV**: Development environment
     - Default URL: `https://cloudblazer2-dev-ed.develop.my.salesforce.com`
   - **STG**: Staging environment
     - Default URL: `https://test.salesforce.com`
   - **PROD**: Production environment
     - Default URL: `https://login.salesforce.com`

2. **Automatic URL Updates:**
   - Selecting an environment automatically updates the Instance URL field
   - The current instance URL is displayed below the field
   - You can still manually edit the Instance URL if needed

3. **Environment Detection:**
   - On page load, the environment is auto-detected based on the current Instance URL
   - Defaults to DEV if URL doesn't match any environment

## Sign Out Functionality

The application includes a Sign Out button that appears after successful authentication:

**Features:**
- Clears OAuth session (for OAuth2 Flow)
- Clears sessionStorage (process IDs, Google Drive tokens)
- Resets the form (all input fields)
- Resets app dropdown to "All Objects (No Filter)"
- Clears load apps status message
- Resets buttons to initial state
- Clears log output
- Resets status indicator
- Stops any running status polling
- Resets instance URL based on selected environment

**Usage:**
1. Click **"Sign Out"** button (appears after authentication)
2. Confirm the sign out action
3. Form is reset and ready for a new session

## Google Drive Integration (Optional)

To enable Google Drive upload functionality:

1. **Create a Google Cloud Project:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Enable the Google Drive API

2. **Create OAuth 2.0 Credentials:**
   - Go to **APIs & Services** → **Credentials**
   - Click **Create Credentials** → **OAuth client ID**
   - Choose **Web application** type
   - Add authorized redirect URIs:
     - `http://localhost:8000/google-drive-callback` (for local development)
     - `https://your-app-name.herokuapp.com/google-drive-callback` (for Heroku)

3. **Set Environment Variables:**
   ```bash
   export GOOGLE_CLIENT_ID="your-client-id"
   export GOOGLE_CLIENT_SECRET="your-client-secret"
   export GOOGLE_REDIRECT_URI="http://localhost:8000/google-drive-callback"
   ```

4. **For Heroku Deployment:**
   ```bash
   heroku config:set GOOGLE_CLIENT_ID="your-client-id"
   heroku config:set GOOGLE_CLIENT_SECRET="your-client-secret"
   # Redirect URI is auto-detected, or set manually:
   heroku config:set GOOGLE_REDIRECT_URI="https://your-app-name.herokuapp.com/google-drive-callback"
   ```

**Note**: This application uses personal Google accounts for authentication (no Google Workspace credentials required), making it suitable for enterprise use where users authenticate with their own Google accounts.

## Lucidchart Integration

The application provides links to Lucidchart for ERD visualization:

1. **Login to Lucidchart:**
   - Click **"Login to Lucidchart"** button on the Lucidchart page
   - Opens Lucidchart login page in a new tab
   - Login with your Lucidchart account

2. **View Charts:**
   - Click **"View Charts"** button to view your Lucidchart documents
   - Opens Lucidchart documents page in a new tab

3. **Import ERD:**
   - Download the Lucidchart CSV file from the application
   - In Lucidchart, go to **Import** → **ERD** → **Import from CSV**
   - Upload the CSV file from your desktop or Google Drive

**Note**: The application no longer uses OAuth2 API integration with Lucidchart. Instead, it provides direct links to Lucidchart pages for login and document viewing.

## Heroku Deployment

### Prerequisites
- Heroku account
- Heroku CLI installed
- Git repository initialized

### Deployment Steps

1. **Login to Heroku:**
   ```bash
   heroku login
   ```

2. **Create a Heroku app:**
   ```bash
   heroku create your-app-name
   ```

3. **Set environment variables in Heroku:**
   ```bash
   heroku config:set SALESFORCE_CLIENT_ID="your-consumer-key"
   heroku config:set SALESFORCE_CLIENT_SECRET="your-consumer-secret"
   heroku config:set DEPLOYMENT_ENV="PROD"  # or STG, DEV
   heroku config:set GOOGLE_CLIENT_ID="your-google-client-id"  # Optional
   heroku config:set GOOGLE_CLIENT_SECRET="your-google-client-secret"  # Optional
   ```

4. **Deploy to Heroku:**
   ```bash
   git push heroku main
   # or git push heroku master (depending on your default branch)
   ```

5. **Open your app:**
   ```bash
   heroku open
   ```

### Important Notes for Heroku:

- The app automatically uses the `PORT` environment variable provided by Heroku
- Input and output directories are created at runtime (Heroku uses an ephemeral filesystem)
- Files generated during a session will be available for download, but will be lost when the dyno restarts
- For persistent storage, use Google Drive upload functionality
- The redirect URI for OAuth2 flows is automatically constructed from your Heroku app URL
- Update Salesforce External Client App callback URL to include your Heroku app URL

### Heroku Files

- `Procfile` - Defines how Heroku runs the application (`web: uvicorn main:app --host 0.0.0.0 --port $PORT`)
- `runtime.txt` - Specifies Python version (e.g., `python-3.11.7`)
- `.slugignore` - Excludes unnecessary files from Heroku slug (reduces slug size)

## Development

### Local Development

To run in development mode with auto-reload:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Or using Python directly:
```bash
python main.py
```

### Heroku Local Testing

To test the app locally with Heroku-like environment:
```bash
heroku local web
```

This will use the `Procfile` and environment variables from `.env` file (if present).

## Troubleshooting

### Common Issues

1. **"Invalid client credentials"**:
   - Verify Client ID and Client Secret are correct
   - Check that the External Client App is activated (wait 2-10 minutes after creation)

2. **"Invalid username or password"** (Password Flow):
   - Check username/password
   - Ensure security token is appended to password with no space
   - Reset security token if needed: Setup → My Personal Information → Reset My Security Token

3. **"redirect_uri_mismatch"** (OAuth2 Flow):
   - Ensure callback URL is configured in Salesforce External Client App
   - Check that the callback URL matches exactly (including protocol and port)
   - Wait 2-10 minutes after updating callback URL

4. **"missing required code challenge"** (OAuth2 Flow):
   - Disable "Require PKCE for Authorization Code Flow" in Salesforce External Client App settings
   - This application does not use PKCE

5. **"IP restricted"**:
   - Configure IP relaxation in External Client App settings
   - Select "Relax IP restrictions" for development/testing

6. **"Insufficient access"**:
   - Ensure user has API access enabled
   - Check object-level permissions
   - User may need "View All Data" permission

7. **No apps in dropdown**:
   - Check that authentication was successful
   - Verify user has access to view apps
   - Try refreshing the page and authenticating again

8. **No objects retrieved for selected app**:
   - Apps without namespace extract all objects (standard Salesforce apps)
   - Apps with namespace only extract objects with that namespace prefix
   - Check that the app has custom objects with the namespace

### Debug Mode

Enable debug mode for more detailed logging:
```bash
export DEBUG="True"
export LOG_LEVEL="DEBUG"
```

## Notes

- The application creates `input/` and `output/` directories automatically
- Processing may take some time depending on the number of objects in your org
- Ensure your Salesforce user has appropriate permissions to access object metadata
- The web interface polls for status updates every second
- Multiple processes can run simultaneously (each with a unique process ID)
- Files can be downloaded directly or uploaded to Google Drive for easy access
- Lucidchart can import files from both desktop downloads and Google Drive
- Sign Out clears all session data and resets the form for a fresh start
- Environment selection automatically updates the instance URL for convenience

## License

[Add your license information here]

## Support

For issues, questions, or contributions, please [add your support contact information or repository link].
