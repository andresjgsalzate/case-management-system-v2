from pydantic import BaseModel, EmailStr, Field


class CreateUserDTO(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=300)
    password: str = Field(min_length=6)
    role_id: str | None = None
    team_id: str | None = None


class UpdateUserDTO(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=300)
    role_id: str | None = None
    team_id: str | None = None
    email_notifications: bool | None = None
    avatar_url: str | None = None


class ChangePasswordDTO(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


class UserResponseDTO(BaseModel):
    id: str
    email: str
    full_name: str
    role_id: str | None
    team_id: str | None
    is_active: bool
    email_notifications: bool
    avatar_url: str | None
    created_at: str

    model_config = {"from_attributes": True}
