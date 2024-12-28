"""User authentication service using simple HTTP Basic Auth."""

from fastapi import HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
import os
import logging

logger = logging.getLogger(__name__)

class SimpleAuthService:
    def __init__(self):
        # Simple user configuration - load from environment or use defaults
        self.users = {
            os.getenv("ADMIN_USERNAME", "admin"): {
                "user_id": 1,
                "password": os.getenv("ADMIN_PASSWORD", "admin123"),
                "name": "Administrator", 
                "role": "admin"
            },
            os.getenv("USER1_USERNAME", "user1"): {
                "user_id": 2,
                "password": os.getenv("USER1_PASSWORD", "user123"),
                "name": "User One",
                "role": "user"
            }
        }
        self.security = HTTPBasic()
    
    def authenticate_user(self, credentials: HTTPBasicCredentials) -> dict:
        """Authenticate user with basic auth."""
        username = credentials.username
        password = credentials.password
        
        # Check if user exists and password matches
        if username in self.users:
            stored_password = self.users[username]["password"]
            # Simple password comparison (use secrets.compare_digest for timing attack protection)
            if secrets.compare_digest(password, stored_password):
                return {
                    "user_id": self.users[username]["user_id"],
                    "username": username,
                    "name": self.users[username]["name"],
                    "role": self.users[username]["role"]
                }
        
        # Authentication failed
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    def get_current_user(self, credentials: HTTPBasicCredentials) -> dict:
        """Get current authenticated user."""
        return self.authenticate_user(credentials)
    
    def require_admin(self, user: dict) -> bool:
        """Check if user has admin role."""
        if user["role"] != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        return True
    
    def get_all_users(self) -> list:
        """Get list of all configured users (for debugging)."""
        return [
            {
                "username": username,
                "name": user_info["name"],
                "role": user_info["role"]
            }
            for username, user_info in self.users.items()
        ] 