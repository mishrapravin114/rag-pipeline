
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from src.config.settings import settings

class GoogleDriveService:
    def __init__(self, user):
        self.user = user
        self.credentials = self._get_credentials()

    def _get_credentials(self):
        if self.user.google_access_token:
            return Credentials(
                token=self.user.google_access_token,
                refresh_token=self.user.google_refresh_token,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=settings.GOOGLE_CLIENT_ID,
                client_secret=settings.GOOGLE_CLIENT_SECRET,
                scopes=['https://www.googleapis.com/auth/drive.readonly']
            )
        return None

    def is_authenticated(self):
        if not self.credentials:
            return False
        
        # Check if credentials are valid and not expired
        if self.credentials.valid:
            return True
        
        # Try to refresh if expired
        if self.credentials.expired and self.credentials.refresh_token:
            try:
                from google.auth.transport.requests import Request
                self.credentials.refresh(Request())
                # Update user's tokens in database
                self.user.google_access_token = self.credentials.token
                from src.database.database import get_db
                db = next(get_db())
                db.commit()
                return True
            except Exception as e:
                print(f"Failed to refresh token: {e}")
                return False
        
        return False

    def get_authorization_url(self, state: str):
        flow = Flow.from_client_secrets_file(
            settings.GOOGLE_CLIENT_SECRETS_FILE,
            scopes=['https://www.googleapis.com/auth/drive.readonly'],
            redirect_uri=f'{settings.BACKEND_URL}/api/auth/google/callback',
            state=state
        )
        authorization_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        return authorization_url

    def fetch_token(self, code: str):
        flow = Flow.from_client_secrets_file(
            settings.GOOGLE_CLIENT_SECRETS_FILE,
            scopes=['https://www.googleapis.com/auth/drive.readonly'],
            redirect_uri=f'{settings.BACKEND_URL}/api/auth/google/callback'
        )
        flow.fetch_token(code=code)
        credentials = flow.credentials
        return {
            'access_token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'expiry': credentials.expiry
        }

    def download_file(self, file_id):
        if not self.is_authenticated():
            raise Exception("User is not authenticated with Google Drive.")

        service = build('drive', 'v3', credentials=self.credentials)
        
        # First, try to get file metadata to check access
        try:
            file_metadata = service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, size, permissions, shared, ownedByMe, sharingUser'
            ).execute()
            file_name = file_metadata.get('name')
            
            # Check if it's a Google Docs file (needs export)
            mime_type = file_metadata.get('mimeType', '')
            if mime_type.startswith('application/vnd.google-apps.'):
                # Export Google Docs files to appropriate format
                export_mime_type = {
                    'application/vnd.google-apps.document': 'application/pdf',
                    'application/vnd.google-apps.spreadsheet': 'application/pdf',
                    'application/vnd.google-apps.presentation': 'application/pdf',
                }.get(mime_type, 'application/pdf')
                
                request = service.files().export_media(
                    fileId=file_id,
                    mimeType=export_mime_type
                )
                # Update filename with extension
                file_name = file_name + '.pdf'
            else:
                # Regular file download
                request = service.files().get_media(fileId=file_id)
            
            file_content = request.execute()
            return file_name, file_content
            
        except Exception as e:
            if '404' in str(e):
                raise Exception(f"File not found or no access permission for file ID: {file_id}")
            else:
                raise Exception(f"Error downloading file: {str(e)}")
    
    def list_files(self, query=None, page_size=10):
        """List files accessible to the user"""
        if not self.is_authenticated():
            raise Exception("User is not authenticated with Google Drive.")
        
        service = build('drive', 'v3', credentials=self.credentials)
        
        # Default query to exclude trashed files
        if not query:
            query = "trashed = false"
        
        try:
            results = service.files().list(
                q=query,
                pageSize=page_size,
                fields="files(id, name, mimeType, modifiedTime, size, shared, ownedByMe)",
                orderBy="modifiedTime desc"
            ).execute()
            
            return results.get('files', [])
        except Exception as e:
            raise Exception(f"Error listing files: {str(e)}")
