"""
Authentication API endpoints for user management
"""
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from database.database import get_db, Users
from services.auth_service import AuthService, ACCESS_TOKEN_EXPIRE_MINUTES
from services.password_utils import hash_password

router = APIRouter(prefix="/api/auth", tags=["authentication"])
security = HTTPBearer()

# Pydantic models
class UserLoginRequest(BaseModel):
    username: str
    password: str

class UserRegistrationRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: Optional[str] = "user"

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    last_login: Optional[datetime]
    created_at: datetime
    google_access_token: Optional[str] = None

class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert minutes to seconds

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class UserProfileUpdate(BaseModel):
    email: Optional[EmailStr] = None

class UserRoleUpdate(BaseModel):
    role: str

class UserStatusUpdate(BaseModel):
    is_active: bool

# Dependency to get current user from token
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Users:
    """
    Get current authenticated user from JWT token
    """
    token = credentials.credentials
    user = AuthService.get_user_from_token(db, token)
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user"
        )
    
    return user

# Dependency to get admin user
async def get_admin_user(current_user: Users = Depends(get_current_user)) -> Users:
    """
    Ensure current user is an admin
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


@router.post("/login", response_model=AuthResponse)
async def login_user(user_data: UserLoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate user and return JWT tokens
    """
    user = AuthService.authenticate_user(db, user_data.username, user_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create tokens
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = AuthService.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    refresh_token = AuthService.create_refresh_token(data={"sub": user.username})
    
    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            last_login=user.last_login,
            created_at=user.created_at,
            google_access_token=user.google_access_token
        )
    )

@router.post("/register", response_model=UserResponse)
async def register_user(
    user_data: UserRegistrationRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user (admin required for non-user roles)
    """
    # Check if username or email already exists
    existing_user = db.query(Users).filter(
        (Users.username == user_data.username) | (Users.email == user_data.email)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )
    
    # Validate role assignment
    if user_data.role not in ["admin", "user", "viewer"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be 'admin', 'user', or 'viewer'"
        )
    
    # For now, allow registration without admin restriction
    # TODO: Add admin restriction for creating admin users
    
    # Create new user
    hashed_password = hash_password(user_data.password)
    new_user = Users(
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password,
        role=user_data.role,
        is_active=True
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return UserResponse(
        id=new_user.id,
        username=new_user.username,
        email=new_user.email,
        role=new_user.role,
        is_active=new_user.is_active,
        last_login=new_user.last_login,
        created_at=new_user.created_at,
        google_access_token=new_user.google_access_token
    )

@router.post("/logout")
async def logout_user(current_user: Users = Depends(get_current_user)):
    """
    Logout user (token will be invalidated on client side)
    """
    return {"message": "Successfully logged out"}

@router.post("/refresh-token")
async def refresh_access_token(refresh_token: str = Form(...)):
    """
    Create new access token and refresh token from refresh token
    """
    tokens = AuthService.refresh_access_token(refresh_token)
    
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert minutes to seconds
    }

@router.get("/profile", response_model=UserResponse)
async def get_user_profile(current_user: Users = Depends(get_current_user)):
    """
    Get current user profile
    """
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        last_login=current_user.last_login,
        created_at=current_user.created_at,
        google_access_token=current_user.google_access_token
    )

@router.put("/profile", response_model=UserResponse)
async def update_user_profile(
    profile_data: UserProfileUpdate,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update current user profile
    """
    if profile_data.email:
        # Check if email is already taken
        existing_user = db.query(Users).filter(
            Users.email == profile_data.email,
            Users.id != current_user.id
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        current_user.email = profile_data.email
    
    current_user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(current_user)
    
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        last_login=current_user.last_login,
        created_at=current_user.created_at,
        google_access_token=current_user.google_access_token
    )

@router.put("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change user password
    """
    from services.password_utils import verify_password
    
    # Verify current password
    if not verify_password(password_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
    
    # Update password
    current_user.password_hash = hash_password(password_data.new_password)
    current_user.updated_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Password updated successfully"}

# Admin endpoints
@router.get("/users", response_model=List[UserResponse])
async def get_all_users(
    admin_user: Users = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get all users (admin only)
    """
    users = db.query(Users).all()
    return [
        UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            last_login=user.last_login,
            created_at=user.created_at
        )
        for user in users
    ]

@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    role_data: UserRoleUpdate,
    admin_user: Users = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Update user role (admin only)
    """
    user = db.query(Users).filter(Users.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if role_data.role not in ["admin", "user", "viewer"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role"
        )
    
    user.role = role_data.role
    user.updated_at = datetime.utcnow()
    db.commit()
    
    return {"message": f"User role updated to {role_data.role}"}

@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: int,
    status_data: UserStatusUpdate,
    admin_user: Users = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Update user status (admin only)
    """
    user = db.query(Users).filter(Users.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.is_active = status_data.is_active
    user.updated_at = datetime.utcnow()
    db.commit()
    
    return {"message": f"User status updated to {'active' if status_data.is_active else 'inactive'}"}

@router.put("/users/{user_id}/profile")
async def admin_update_user_profile(
    user_id: int,
    profile_data: UserProfileUpdate,
    admin_user: Users = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Admin update user profile (admin only)
    """
    user = db.query(Users).filter(Users.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if profile_data.email:
        # Check if email is already taken
        existing_user = db.query(Users).filter(
            Users.email == profile_data.email,
            Users.id != user_id
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        user.email = profile_data.email
    
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        last_login=user.last_login,
        created_at=user.created_at
    )

@router.post("/users/{user_id}/reset-password")
async def admin_reset_user_password(
    user_id: int,
    admin_user: Users = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Admin reset user password (admin only)
    """
    import secrets
    import string
    
    user = db.query(Users).filter(Users.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Generate secure temporary password
    alphabet = string.ascii_letters + string.digits
    temp_password = ''.join(secrets.choice(alphabet) for i in range(12))
    
    # Update password
    user.password_hash = hash_password(temp_password)
    user.updated_at = datetime.utcnow()
    db.commit()
    
    return {
        "message": "Password reset successfully",
        "temporary_password": temp_password,
        "note": "User should change this password on next login"
    }

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin_user: Users = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Delete user (admin only) - soft delete by deactivating
    """
    user = db.query(Users).filter(Users.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent self-deletion
    if user.id == admin_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    # Soft delete by deactivating
    user.is_active = False
    user.updated_at = datetime.utcnow()
    db.commit()
    
    return {"message": f"User '{user.username}' has been deactivated"}

@router.get("/analytics/users")
async def get_user_analytics(
    admin_user: Users = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get user analytics data (admin only)
    """
    from sqlalchemy import func, case
    from datetime import datetime, timedelta
    
    # Total users
    total_users = db.query(Users).count()
    
    # Active/Inactive breakdown
    active_users = db.query(Users).filter(Users.is_active == True).count()
    inactive_users = total_users - active_users
    
    # Role distribution
    role_distribution = db.query(
        Users.role,
        func.count(Users.id).label('count')
    ).group_by(Users.role).all()
    
    # Recent registrations (last 7 days)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_registrations = db.query(Users).filter(
        Users.created_at >= seven_days_ago
    ).count()
    
    # Users with recent login activity (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    active_last_30_days = db.query(Users).filter(
        Users.last_login >= thirty_days_ago
    ).count()
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": inactive_users,
        "role_distribution": {role: count for role, count in role_distribution},
        "recent_registrations": recent_registrations,
        "active_last_30_days": active_last_30_days,
        "generated_at": datetime.utcnow()
    } 