from pydantic import BaseModel, Field


class CreateCasePriorityDTO(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    level: int = Field(ge=1, le=10)
    color: str = "#6B7280"
    is_default: bool = False


class CasePriorityResponseDTO(BaseModel):
    id: str
    name: str
    level: int
    color: str
    is_default: bool
    is_active: bool

    class Config:
        from_attributes = True
