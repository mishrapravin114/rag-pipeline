"""Simple authentication router using HTTP Basic Auth."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from typing import Optional
from api.services.simple_auth_service import SimpleAuthService

router = APIRouter(prefix="/api/auth", tags=["authentication"])
auth_service = SimpleAuthService()

# Pydantic model for JSON login requests
class LoginRequest(BaseModel):
    username: str
    password: str

@router.get("/me")
async def get_current_user(credentials: HTTPBasicCredentials = Depends(auth_service.security)):
    """Get current authenticated user info."""
    user = auth_service.get_current_user(credentials)
    return {
        "username": user["username"],
        "name": user["name"],
        "role": user["role"],
        "authenticated": True
    }

@router.post("/check")
async def check_auth(credentials: HTTPBasicCredentials = Depends(auth_service.security)):
    """Simple auth check endpoint."""
    user = auth_service.get_current_user(credentials)
    return {
        "authenticated": True,
        "user": user
    }

@router.post("/login")
async def login(login_request: LoginRequest):
    """Login endpoint for frontend compatibility - handles JSON body authentication."""
    try:
        # Create credentials object from JSON body
        fake_credentials = HTTPBasicCredentials(
            username=login_request.username, 
            password=login_request.password
        )
        user = auth_service.get_current_user(fake_credentials)
        
        return {
            "success": True,
            "user": {
                "id": user["user_id"],
                "username": user["username"],
                "name": user["name"],
                "role": user["role"]
            },
            "message": "Login successful"
        }
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

@router.post("/logout")
async def logout():
    """Logout endpoint for frontend compatibility."""
    return {
        "success": True,
        "message": "Logout successful"
    }

@router.get("/users")
async def list_users(
    credentials: HTTPBasicCredentials = Depends(auth_service.security)
):
    """List all configured users (admin only)."""
    user = auth_service.get_current_user(credentials)
    auth_service.require_admin(user)
    
    return {
        "users": auth_service.get_all_users()
    }

# Helper functions for protecting routes
def get_current_user(credentials: HTTPBasicCredentials = Depends(auth_service.security)):
    """Dependency for protecting routes."""
    return auth_service.get_current_user(credentials)

def require_admin(user: dict = Depends(get_current_user)):
    """Dependency for admin-only routes."""
    auth_service.require_admin(user)
    return user 