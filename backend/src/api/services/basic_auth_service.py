from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
from typing import Dict, Any

class BasicAuthService:
    def __init__(self):
        self.security = HTTPBasic()
        
        # Simple user store (replace with database in production)
        self.users = {
            "admin": {
                "id": "1",
                "username": "admin",
                "name": "Administrator", 
                "role": "admin",
                "password": "admin123"  # Change this in production
            },
            "user1": {
                "id": "2", 
                "username": "user1",
                "name": "User One",
                "role": "user",
                "password": "user123"  # Change this in production
            },
            "demo": {
                "id": "3",
                "username": "demo",
                "name": "Demo User",
                "role": "user", 
                "password": "demo123"
            }
        }
    
    def authenticate_user(self, credentials: HTTPBasicCredentials) -> Dict[str, Any]:
        """Authenticate user with basic auth."""
        username = credentials.username
        password = credentials.password
        
        # Check if user exists and password matches
        if username in self.users:
            stored_password = self.users[username]["password"]
            # Use secrets.compare_digest for timing attack protection
            if secrets.compare_digest(password, stored_password):
                return self.users[username]
        
        # Authentication failed
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    def get_current_user(self, credentials: HTTPBasicCredentials) -> Dict[str, Any]:
        """Get current authenticated user."""
        return self.authenticate_user(credentials)
    
    def require_admin(self, user: Dict[str, Any]) -> bool:
        """Check if user has admin role."""
        if user["role"] != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        return True 