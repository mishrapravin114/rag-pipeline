from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from src.database.database import get_db, Users
from src.services.google_drive_service import GoogleDriveService
from src.api.routers.auth import get_current_user
from src.api.state import oauth_state_store
import logging
import uuid
from pathlib import Path

router = APIRouter()
logger = logging.getLogger(__name__)
UPLOAD_DIR = Path("./uploads")

@router.get("/auth/google/auth-url")
async def get_google_auth_url(current_user: Users = Depends(get_current_user), db: Session = Depends(get_db)):
    # Clear existing Google tokens to force fresh authentication
    current_user.google_access_token = None
    current_user.google_refresh_token = None
    current_user.google_token_expiry = None
    db.commit()
    logger.info(f"Cleared Google tokens for user {current_user.username}")
    
    state = str(uuid.uuid4())
    oauth_state_store[state] = current_user.id
    logger.info(f"Generated new OAuth state: {state} for user {current_user.username} (ID: {current_user.id})")
    logger.info(f"State store now contains: {list(oauth_state_store.keys())}")
    
    service = GoogleDriveService(current_user)
    authorization_url = service.get_authorization_url(state)
    logger.info(f"Generated auth URL: {authorization_url}")
    return {"url": authorization_url}

@router.get("/auth/google/callback")
async def google_callback(code: str, state: str, db: Session = Depends(get_db)):
    logger.info(f"Google callback received with state: {state}")
    logger.info(f"Current state store keys: {list(oauth_state_store.keys())}")
    
    if state not in oauth_state_store:
        logger.error(f"State {state} not found in oauth_state_store")
        raise HTTPException(status_code=400, detail="Invalid state parameter.")
    
    user_id = oauth_state_store.pop(state)
    user = db.query(Users).filter(Users.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    service = GoogleDriveService(user)
    token_data = service.fetch_token(code)
    
    user.google_access_token = token_data['access_token']
    user.google_refresh_token = token_data['refresh_token']
    user.google_token_expiry = token_data['expiry']
    
    db.commit()
    
    return HTMLResponse(content="<html><body><h1>Authentication successful!</h1><p>You can close this window.</p></body></html>")

@router.get("/auth/google/status")
async def google_auth_status(current_user: Users = Depends(get_current_user)):
    service = GoogleDriveService(current_user)
    return {"authenticated": service.is_authenticated()}

@router.get("/auth/google/debug-access")
async def debug_google_access(current_user: Users = Depends(get_current_user)):
    """Debug endpoint to check what files user can access"""
    service = GoogleDriveService(current_user)
    if not service.is_authenticated():
        return {"error": "Not authenticated with Google Drive"}
    
    try:
        # List some accessible files
        files = service.list_files(page_size=5)
        
        # Get more info about the token
        return {
            "authenticated": True,
            "accessible_files": files,
            "token_info": {
                "has_token": bool(current_user.google_access_token),
                "token_length": len(current_user.google_access_token) if current_user.google_access_token else 0,
                "has_refresh_token": bool(current_user.google_refresh_token)
            }
        }
    except Exception as e:
        return {"error": str(e)}

@router.post("/files/upload_from_google_drive")
async def upload_from_google_drive(request: Request, db: Session = Depends(get_db), current_user: Users = Depends(get_current_user)):
    body = await request.json()
    file_ids = body.get("fileIds")

    if not file_ids:
        raise HTTPException(status_code=400, detail="No file IDs provided.")

    service = GoogleDriveService(current_user)
    if not service.is_authenticated():
        raise HTTPException(status_code=401, detail="User is not authenticated with Google Drive.")

    downloaded_files = []
    failed_files = []
    
    for file_id in file_ids:
        try:
            logger.info(f"Attempting to download file: {file_id} for user: {current_user.username}")
            file_name, file_content = service.download_file(file_id)
            
            unique_filename = f"{uuid.uuid4()}_{file_name}"
            file_path = UPLOAD_DIR / unique_filename
            with open(file_path, "wb") as f:
                f.write(file_content)

            from src.database.database import SourceFiles
            source_file = SourceFiles(
                file_name=file_name,
                file_url=f"/uploads/{unique_filename}",
                status="PENDING",
                created_by=current_user.id
            )
            db.add(source_file)
            db.commit()
            db.refresh(source_file)

            file_info = {
                "originalFileName": file_name,
                "serverFileName": unique_filename,
                "serverUrl": f"/uploads/{unique_filename}",
                "fileSize": len(file_content),
                "id": source_file.id  # Add the file ID for collection addition
            }
            logger.info(f"Added file to response: {file_info}")
            downloaded_files.append(file_info)
        except Exception as e:
            logger.error(f"Failed to download file {file_id}: {e}")
            failed_files.append({
                "fileId": file_id,
                "error": str(e)
            })

    return {
        "downloadedFiles": downloaded_files,
        "failedFiles": failed_files,
        "totalRequested": len(file_ids),
        "totalDownloaded": len(downloaded_files),
        "totalFailed": len(failed_files)
    }