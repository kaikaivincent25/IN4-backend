from typing import Literal

from pydantic import EmailStr, Field, field_validator, model_validator

from app.db.schemas.common import RequestSchema, ResponseSchema
from app.db.schemas.users import UserPublic, UserRead


class RegisterRequest(RequestSchema):
    email: EmailStr
    password: str = Field(min_length=8)
    password_confirm: str = Field(min_length=8)
    first_name: str = Field(min_length=1, max_length=150)
    last_name: str = Field(min_length=1, max_length=150)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

    @field_validator("password")
    @classmethod
    def reject_uniform_passwords(cls, value: str) -> str:
        if value.isnumeric() or value.isalpha():
            raise ValueError("Password cannot be entirely numeric or alphabetic.")
        return value

    @model_validator(mode="after")
    def passwords_match(self) -> "RegisterRequest":
        if self.password != self.password_confirm:
            raise ValueError("Passwords do not match.")
        return self


class LoginRequest(RequestSchema):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class TokenRefreshRequest(RequestSchema):
    refresh: str = Field(min_length=1)


class TokenPair(ResponseSchema):
    access: str
    refresh: str


class TokenRefreshResponse(ResponseSchema):
    status: Literal["success"] = "success"
    access: str


class AuthResponse(ResponseSchema):
    status: Literal["success"] = "success"
    message: str
    user: UserPublic
    tokens: TokenPair


class ProfileUpdateRequest(RequestSchema):
    first_name: str | None = Field(default=None, min_length=1, max_length=150)
    last_name: str | None = Field(default=None, min_length=1, max_length=150)


class ProfileResponse(ResponseSchema):
    status: Literal["success"] = "success"
    message: str | None = None
    user: UserRead


class ChangePasswordRequest(RequestSchema):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)
    new_password_confirm: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def reject_uniform_passwords(cls, value: str) -> str:
        if value.isnumeric() or value.isalpha():
            raise ValueError("Password cannot be entirely numeric or alphabetic.")
        return value

    @model_validator(mode="after")
    def passwords_match(self) -> "ChangePasswordRequest":
        if self.new_password != self.new_password_confirm:
            raise ValueError("Passwords do not match.")
        return self


class MessageResponse(ResponseSchema):
    status: Literal["success", "info"] = "success"
    message: str
