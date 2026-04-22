from pydantic import BaseModel
from uuid import UUID

class UserRegister(BaseModel):
    email: str
    password: str

class UserLogin(BaseModel):
    password: str
    email: str

class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: UUID
    email: str
    
class RefreshTokenRequest(BaseModel):
    refresh_token: str