from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    email: EmailStr


class MessageResponse(BaseModel):
    message: str


# Backwards-compatible aliases
LoginResponse = MessageResponse


class LoginServiceResult(BaseModel):
    access_token: str
