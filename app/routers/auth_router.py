from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from typing import Optional
from jose import jwt, JWTError
from datetime import datetime, timedelta
import hashlib
import os
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from app.db import db

router = APIRouter()

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return f"{salt.hex()}:{key.hex()}"

def verify_password(password: str, hashed_password: str) -> bool:
    try:
        salt_hex, key_hex = hashed_password.split(':')
        salt = bytes.fromhex(salt_hex)
        key = bytes.fromhex(key_hex)
        new_key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return new_key == key
    except Exception:
        return False

# JWT configuration
JWT_SECRET = os.getenv("JWT_SECRET", "gordon_jwt_secret_key_extremely_secure_12345")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

class RegisterSchema(BaseModel):
    email: EmailStr
    password: str

class LoginSchema(BaseModel):
    email: EmailStr
    password: str

class GoogleLoginSchema(BaseModel):
    id_token: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    membership_level: str
    email: str

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = await db.user.find_unique(where={"email": email})
    if user is None:
        raise credentials_exception
    return user

@router.post("/register", response_model=TokenResponse)
async def register(data: RegisterSchema):
    # Check if user already exists
    existing_user = await db.user.find_unique(where={"email": data.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
        
    # Create new user
    hashed_password = hash_password(data.password)
    user = await db.user.create(
        data={
            "email": data.email,
            "passwordHash": hashed_password,
            "membershipLevel": "free"
        }
    )
    
    # Generate token
    access_token = create_access_token(data={"sub": user.email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "membership_level": user.membershipLevel,
        "email": user.email
    }

@router.post("/login", response_model=TokenResponse)
async def login(data: OAuth2PasswordRequestForm = Depends()):
    # Note: OAuth2PasswordRequestForm uses 'username' instead of 'email'
    user = await db.user.find_unique(where={"email": data.username})
    
    if not user or not user.passwordHash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
        
    if not verify_password(data.password, user.passwordHash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
        
    access_token = create_access_token(data={"sub": user.email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "membership_level": user.membershipLevel,
        "email": user.email
    }

@router.post("/google", response_model=TokenResponse)
async def google_login(data: GoogleLoginSchema):
    email = None
    google_id = None
    
    # Check if it is a dummy token for local testing
    if data.id_token.startswith("dummy_google_"):
        # Format: dummy_google_email@example.com_googleid123
        parts = data.id_token.split("_")
        if len(parts) >= 4:
            email = parts[2]
            google_id = parts[3]
        else:
            email = "testgoogleuser@example.com"
            google_id = "1234567890"
    else:
        # Real google login token verification
        try:
            from google.oauth2 import id_token
            from google.auth.transport import requests as google_requests
            
            client_id = os.getenv("GOOGLE_CLIENT_ID")
            idinfo = id_token.verify_oauth2_token(data.id_token, google_requests.Request(), client_id)
            
            email = idinfo["email"]
            google_id = idinfo["sub"]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid Google ID token: {str(e)}"
            )
            
    # Check if user already exists
    user = await db.user.find_unique(where={"email": email})
    
    if not user:
        # Register new Google user
        user = await db.user.create(
            data={
                "email": email,
                "googleId": google_id,
                "membershipLevel": "free"
            }
        )
    elif not user.googleId:
        # Link google account if standard email user exists
        user = await db.user.update(
            where={"email": email},
            data={"googleId": google_id}
        )
        
    access_token = create_access_token(data={"sub": user.email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "membership_level": user.membershipLevel,
        "email": user.email
    }

@router.get("/me")
async def get_me(current_user = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "membership_level": current_user.membershipLevel,
        "createdAt": current_user.createdAt
    }
