"""
JWT Authentication service for user authentication and authorization
"""
import os
from datetime import datetime, timedelta
from typing import Optional, Union
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from database.database import Users, get_db_session
from services.password_utils import verify_password
import secrets

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours default (was 4 hours)
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "90"))       # 90 days default (was 30 days)

class AuthService:
    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> Optional[Users]:
        """
        Authenticate user with username and password
        
        Args:
            db: Database session
            username: Username or email
            password: Plain text password
            
        Returns:
            User object if authentication successful, None otherwise
        """
        # Try to find user by username or email
        user = db.query(Users).filter(
            (Users.username == username) | (Users.email == username)
        ).first()
        
        if not user:
            return None
        
        if not user.is_active:
            return None
            
        if not verify_password(password, user.password_hash):
            return None
            
        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()
        
        return user
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        Create JWT access token
        
        Args:
            data: Data to encode in token
            expires_delta: Token expiration time
            
        Returns:
            JWT token string
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(data: dict) -> str:
        """
        Create JWT refresh token
        
        Args:
            data: Data to encode in token
            
        Returns:
            JWT refresh token string
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Optional[dict]:
        """
        Verify and decode JWT token
        
        Args:
            token: JWT token string
            token_type: Expected token type ("access" or "refresh")
            
        Returns:
            Decoded token payload or None if invalid
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            
            # Check token type
            if payload.get("type") != token_type:
                return None
                
            # Check expiration
            exp = payload.get("exp")
            if exp is None:
                return None
                
            if datetime.utcnow() > datetime.fromtimestamp(exp):
                return None
                
            return payload
            
        except JWTError:
            return None
    
    @staticmethod
    def get_user_from_token(db: Session, token: str) -> Optional[Users]:
        """
        Get user from JWT token
        
        Args:
            db: Database session
            token: JWT token string
            
        Returns:
            User object or None if invalid token
        """
        payload = AuthService.verify_token(token)
        if payload is None:
            return None
            
        username = payload.get("sub")
        if username is None:
            return None
            
        user = db.query(Users).filter(Users.username == username).first()
        return user
    
    @staticmethod
    def refresh_access_token(refresh_token: str) -> Optional[dict]:
        """
        Create new access token and refresh token from refresh token
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            Dict with new tokens or None if refresh token invalid
        """
        payload = AuthService.verify_token(refresh_token, "refresh")
        if payload is None:
            return None
            
        username = payload.get("sub")
        if username is None:
            return None
            
        # Create new access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = AuthService.create_access_token(
            data={"sub": username}, expires_delta=access_token_expires
        )
        
        # Create new refresh token for security
        new_refresh_token = AuthService.create_refresh_token(data={"sub": username})
        
        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token
        } 