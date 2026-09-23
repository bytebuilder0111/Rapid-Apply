from pydantic import BaseModel, EmailStr

from app.users.schemas import UserOut


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
