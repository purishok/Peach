import re

from pydantic import BaseModel, Field, field_validator


class AccountCredentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip().lower()
            if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
                raise ValueError("Enter a valid email address")
        return value


class LocalSignUp(AccountCredentials):
    name: str = Field(min_length=1, max_length=200)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class LocalAccount(BaseModel):
    email: str
    name: str


class LocalAuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: LocalAccount
