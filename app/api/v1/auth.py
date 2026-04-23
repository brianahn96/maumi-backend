from fastapi import Depends, HTTPException, status, APIRouter, Cookie
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi import Request
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, timezone
from uuid import UUID
import jwt
import bcrypt
import os
import time
from urllib.parse import urlencode

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Uuid, select
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import redis.asyncio as redis

from app.deps.dependencies import get_db, get_redis_manager
from app.db.models import User, AuthProvider
from app.db.redis import RedisDB
from app.core.config import config
from app.schemas.authentication import UserRegister, UserLogin, AccessTokenResponse, UserResponse, RefreshTokenRequest

SECRET_KEY = config.SECRET_KEY.get_secret_value()
ENVIRONMENT = config.ENVIRONMENT
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

REDIS_DB = 1 if config.ENVIRONMENT == "production" else 0

# OAuth2 Configuration
# GOOGLE_CLIENT_ID = config.GOOGLE_CLIENT_ID.get_secret_value()
# GOOGLE_CLIENT_SECRET = config.GOOGLE_CLIENT_SECRET.get_secret_value()
# NAVER_CLIENT_ID = config.NAVER_CLIENT_ID.get_secret_value()
# NAVER_CLIENT_SECRET = config.NAVER_CLIENT_SECRET.get_secret_value()

    
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())

LOGIN_ATTEMPT_WINDOW = 300  # 5 minutes
MAX_LOGIN_ATTEMPTS = 5

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "type": "access",
        "jti": str(int(time.time() * 1000000)),  # Unique token identifier
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(user_id: str, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "type": "refresh",
        "jti": str(int(time.time() * 1000000)),  # Unique token identifier
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "iat": datetime.now(timezone.utc)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token

async def is_token_blacklisted(token_jti: str, redis: redis.Redis) -> bool:
    blacklisted = await redis.get(f"blacklisted_token:{token_jti}")
    return blacklisted is not None

async def blacklist_token(token_jti: str, exp_time: timedelta, redis: redis.Redis):
    await redis.setex(f"blacklisted_token:{token_jti}", exp_time, "1")

def verify_token(token: str, token_type: str, redis: redis.Redis = None) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        if payload.get("type") != token_type:
            raise jwt.InvalidTokenError("Token type mismatch")

        # Check if token is blacklisted (if redis is provided)
        if redis and "jti" in payload:
            token_jti = payload["jti"]
            # We'll check blacklisting in the calling function since it's async
            pass

        return payload

    except jwt.ExpiredSignatureError:
        raise
    except jwt.InvalidTokenError:
        raise
    except Exception as e:
        raise jwt.InvalidTokenError(f"Token verification failed: {str(e)}")

async def check_rate_limit(username: str, redis: redis.Redis) -> bool:
    key = f"login_attempts:{username}"
    attempts = await redis.get(key)

    if attempts is None:
        # First attempt in this window, set counter with expiry
        await redis.setex(key, LOGIN_ATTEMPT_WINDOW, 1)
        return True

    attempts = int(attempts)
    if attempts >= MAX_LOGIN_ATTEMPTS:
        return False  # Rate limit exceeded

    # Increment attempt count
    await redis.incr(key)
    return True
    
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    redis: redis.Redis = Depends(get_redis_manager(REDIS_DB))
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        token_jti: str = payload.get("jti")

        if token_type != "access" or user_id is None or token_jti is None:
            raise credentials_exception

        # Check if token is blacklisted
        if await is_token_blacklisted(token_jti, redis):
            raise credentials_exception

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise credentials_exception

    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive"
        )

    return user

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)

@router.post("/register")
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    existing_user = await db.execute(
        select(User).where(
            (User.email == user_data.email)
        )
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists"
        )
    
    new_user = User(
        email=user_data.email,
        provider=AuthProvider.local,
        hashed_password=hash_password(user_data.password)
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return new_user

@router.get("/me", response_model=UserResponse)
async def me(
    user: User = Depends(get_current_user)
):
    return UserResponse(id=user.id, email=user.email)

@router.post("/login", response_model=AccessTokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
    redis: redis.Redis = Depends(get_redis_manager(REDIS_DB))
):

    result = await db.execute(
        select(User).where(User.email == form_data.username)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        # Increment rate limit counter even for failed authentication
        # This is handled in check_rate_limit, so we just raise the exception
        
        if not await check_rate_limit(form_data.username, redis):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Please try again later."
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Reset rate limit counter on successful login
    await redis.delete(f"login_attempts:{form_data.username}")

    # Update last login timestamp
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(user_id=user.id, email=user.email)
    refresh_token = create_refresh_token(user_id=user.id, email=user.email)

    try:
        await redis.setex(
            name=f"refresh_token:{user.id}",
            time=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
            value=refresh_token
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not store session"
        )

    response = JSONResponse(
        content={
            "access_token": access_token,
            "token_type": "bearer"
        },
        status_code=status.HTTP_200_OK
    )

    
    # Set secure=True if running in production (behind HTTPS)
    # For development, you can set this based on environment
    is_secure = ENVIRONMENT == "production"

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=is_secure,  # Set to True in production
        samesite="none",
        path="/"
    )

    return response
    
@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh_token(
    refresh_token: str = Cookie(None),
    redis: redis.Redis = Depends(get_redis_manager(REDIS_DB)),
):
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found",
        )

    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise jwt.InvalidTokenError("Token type mismatch")

        user_id: str = payload.get("sub")
        email: str = payload.get("email")
        token_jti: str = payload.get("jti")

        if not user_id or not email or not token_jti:
            raise jwt.InvalidTokenError("Missing required token claims")

        # Check if the refresh token is blacklisted
        if await is_token_blacklisted(token_jti, redis):
            raise jwt.InvalidTokenError("Token has been revoked")

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

    stored_token = await redis.get(f"refresh_token:{user_id}")
    if not stored_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired or revoked",
        )

    if stored_token != refresh_token:
        await redis.delete(f"refresh_token:{user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token mismatch",
        )

    new_access_token = create_access_token(
        user_id=user_id,
        email=email
    )

    new_refresh_token = create_refresh_token(
        user_id=user_id,
        email=email
    )

    # Store the new refresh token
    await redis.setex(
        name=f"refresh_token:{user_id}",
        time=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        value=new_refresh_token
    )
    response = JSONResponse(
        content={
            "access_token": new_access_token,
            "token_type": "bearer"
        },
        status_code=status.HTTP_200_OK
    )
    
    # Set secure=True if running in production (behind HTTPS)
    is_secure = ENVIRONMENT == "production"

    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=is_secure,  # Set to True in production
        samesite="none",
        path="/"
    )

    return response

@router.post("/logout")
async def logout(
    token: str = Depends(oauth2_scheme),
    user: User = Depends(get_current_user),
    redis: redis.Redis = Depends(get_redis_manager(REDIS_DB)),
):
    # Get the token payload to extract jti for blacklisting
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        token_jti = payload.get("jti")

        if token_jti:
            # Calculate remaining time until token expiration
            exp_timestamp = payload.get("exp")
            if exp_timestamp:
                remaining_time = timedelta(seconds=max(0, exp_timestamp - int(datetime.now(timezone.utc).timestamp())))
                await blacklist_token(token_jti, remaining_time, redis)
    except jwt.InvalidTokenError:
        # If token is invalid, we can still proceed with logout
        pass

    # Delete the stored refresh token
    await redis.delete(f"refresh_token:{user.id}")

    response = JSONResponse(
        content={"detail": "Logged out successfully"},
        status_code=status.HTTP_200_OK
    )

    response.delete_cookie(
        key="refresh_token",
        path="/",
        samesite="none"
    )

    return response

# async def get_google_user_info(access_token: str) -> dict:
#     """Get user info from Google"""
#     async with httpx.AsyncClient() as client:
#         response = await client.get(
#             'https://www.googleapis.com/oauth2/v2/userinfo',
#             headers={'Authorization': f'Bearer {access_token}'}
#         )
#         response.raise_for_status()
#         data = response.json()
#         return {
#             'id': data.get('id'),
#             'email': data.get('email'),
#             'name': data.get('name'),
#             'picture': data.get('picture')
#         }

# async def get_naver_user_info(access_token: str) -> dict:
#     """Get user info from Naver"""
#     async with httpx.AsyncClient() as client:
#         response = await client.get(
#             'https://openapi.naver.com/v1/nid/me',
#             headers={'Authorization': f'Bearer {access_token}'}
#         )
#         response.raise_for_status()
#         data = response.json()
#         # Naver 응답 형식 변환
#         user_info = data.get('response', {})
#         return {
#             'id': user_info.get('id'),
#             'email': user_info.get('email'),
#             'name': user_info.get('name'),
#             'picture': user_info.get('profile_image')
#         }

# async def exchange_oauth_code(provider: str, code: str, redirect_uri: str) -> dict:
#     """Exchange authorization code for access token"""
#     async with httpx.AsyncClient() as client:
#         if provider == 'google':
#             response = await client.post(
#                 'https://oauth2.googleapis.com/token',
#                 data={
#                     'code': code,
#                     'client_id': GOOGLE_CLIENT_ID,
#                     'client_secret': GOOGLE_CLIENT_SECRET,
#                     'redirect_uri': redirect_uri,
#                     'grant_type': 'authorization_code'
#                 }
#             )
#         elif provider == 'naver':
#             response = await client.post(
#                 'https://nid.naver.com/oauth2.0/token',
#                 data={
#                     'code': code,
#                     'client_id': NAVER_CLIENT_ID,
#                     'client_secret': NAVER_CLIENT_SECRET,
#                     'redirect_uri': redirect_uri,
#                     'grant_type': 'authorization_code',
#                     'state': 'STATE_STRING'
#                 }
#             )
#         else:
#             raise HTTPException(status_code=400, detail="Invalid provider")

#         response.raise_for_status()
#         return response.json()

# async def get_or_create_oauth_user(
#     db: AsyncSession,
#     provider: str,
#     user_info: dict
# ) -> User:
#     """Get or create user from OAuth provider"""
#     provider_id = str(user_info.get('id'))
#     email = user_info.get('email')
#     name = user_info.get('name') or user_info.get('email', '').split('@')[0]  # Fallback to email prefix for name
#     avatar_url = user_info.get('picture')

#     # Check if user already exists with this provider ID
#     result = await db.execute(
#         select(User).where(
#             (User.provider == AuthProvider[provider]) &
#             (User.provider_user_id == provider_id)
#         )
#     )
#     user = result.scalar_one_or_none()

#     if not user:
#         # Check if user exists with this email (for linking accounts)
#         result = await db.execute(
#             select(User).where(User.email == email)
#         )
#         user = result.scalar_one_or_none()

#         if not user:
#             # Create new user
#             user = User(
#                 email=email,
#                 username=name,
#                 provider=AuthProvider[provider],
#                 provider_user_id=provider_id,
#                 avatar_url=avatar_url
#             )
#             db.add(user)
#         else:
#             # Update existing user with OAuth provider info
#             user.provider = AuthProvider[provider]
#             user.provider_user_id = provider_id

#     # Update user info from OAuth
#     user.username = name
#     user.avatar_url = avatar_url
#     user.is_active = True

#     # Only update last_login_at if we have a current time
#     from datetime import datetime, timezone
#     user.last_login_at = datetime.now(timezone.utc)

#     await db.commit()
#     await db.refresh(user)

#     return user

# @router.get("/naver")
# async def naver_login(request: Request):
#     """Redirect to Naver OAuth authorization"""
#     redirect_uri = str(request.url_for('naver_callback'))
#     params = {
#         'client_id': NAVER_CLIENT_ID,
#         'redirect_uri': redirect_uri,
#         'response_type': 'code',
#         'state': 'STATE_STRING'
#     }
#     return RedirectResponse(url=f'https://nid.naver.com/oauth2.0/authorize?{urlencode(params)}')

# @router.get("/naver/callback")
# async def naver_callback(
#     code: str,
#     state: str,
#     request: Request,
#     db: AsyncSession = Depends(get_db),
#     redis: redis.Redis = Depends(get_redis_manager(REDIS_DB))
# ):
#     """Handle Naver OAuth callback"""
#     # Reconstruct the callback URL properly
#     redirect_uri = f"{request.url.scheme}://{request.url.netloc}{request.url.path}"
#     try:
#         token_data = await exchange_oauth_code('naver', code, redirect_uri)
#         access_token = token_data.get('access_token')

#         user_info = await get_naver_user_info(access_token)
#         user = await get_or_create_oauth_user(db, 'naver', user_info)

#         jwt_access = create_access_token(user_id=str(user.id), email=user.email)
#         jwt_refresh = create_refresh_token(user_id=str(user.id), email=user.email)

#         # Store refresh token in Redis
#         try:
#             await redis.setex(
#                 name=f"refresh_token:{user.id}",
#                 time=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
#                 value=jwt_refresh
#             )
#         except Exception as e:
#             raise HTTPException(
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#                 detail="Could not store session"
#             )

#         response = JSONResponse(
#             content={
#                 "access_token": jwt_access,
#                 "token_type": "bearer"
#             },
#             status_code=status.HTTP_200_OK
#         )

#         # Set secure=True if running in production (behind HTTPS)
#         is_secure = ENVIRONMENT == "production"

#         response.set_cookie(
#             key="refresh_token",
#             value=jwt_refresh,
#             max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
#             httponly=True,
#             secure=is_secure,  # Set to True in production
#             samesite="none",
#             path="/"
#         )

#         return response
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=f"Naver OAuth error: {str(e)}")

# @router.get("/google")
# async def google_login(request: Request):
#     """Redirect to Google OAuth consent screen"""
#     redirect_uri = str(request.url_for('google_callback'))
#     params = {
#         'client_id': GOOGLE_CLIENT_ID,
#         'redirect_uri': redirect_uri,
#         'response_type': 'code',
#         'scope': 'openid email profile',
#         'access_type': 'offline'
#     }
#     return RedirectResponse(url=f'https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}')

# @router.get("/google/callback")
# async def google_callback(
#     code: str,
#     request: Request,
#     db: AsyncSession = Depends(get_db),
#     redis: redis.Redis = Depends(get_redis_manager(REDIS_DB))
# ):
#     """Handle Google OAuth callback"""
#     # Reconstruct the callback URL properly
#     redirect_uri = f"{request.url.scheme}://{request.url.netloc}{request.url.path}"
#     try:
#         token_data = await exchange_oauth_code('google', code, redirect_uri)
#         access_token = token_data.get('access_token')

#         user_info = await get_google_user_info(access_token)
#         user = await get_or_create_oauth_user(db, 'google', user_info)

#         jwt_access = create_access_token(user_id=str(user.id), email=user.email)
#         jwt_refresh = create_refresh_token(user_id=str(user.id), email=user.email)

#         # Store refresh token in Redis
#         try:
#             await redis.setex(
#                 name=f"refresh_token:{user.id}",
#                 time=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
#                 value=jwt_refresh
#             )
#         except Exception as e:
#             raise HTTPException(
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#                 detail="Could not store session"
#             )

#         response = JSONResponse(
#             content={
#                 "access_token": jwt_access,
#                 "token_type": "bearer"
#             },
#             status_code=status.HTTP_200_OK
#         )

#         # Set secure=True if running in production (behind HTTPS)
#         is_secure = ENVIRONMENT == "production"

#         response.set_cookie(
#             key="refresh_token",
#             value=jwt_refresh,
#             max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
#             httponly=True,
#             secure=is_secure,  # Set to True in production
#             samesite="none",
#             path="/"
#         )

#         return response
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=f"Google OAuth error: {str(e)}")


