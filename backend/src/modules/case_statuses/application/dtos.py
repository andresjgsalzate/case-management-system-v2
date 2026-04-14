from pydantic import BaseModel, Field


class CreateCaseStatusDTO(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    color: str = "#6B7280"
    order: int = 0
    is_initial: bool = False
    is_final: bool = False
    pauses_sla: bool = False
    allowed_transitions: list[str] = []


class UpdateCaseStatusDTO(BaseModel):
    name: str | None = None
    color: str | None = None
    order: int | None = None
    is_initial: bool | None = None
    is_final: bool | None = None
    pauses_sla: bool | None = None
    allowed_transitions: list[str] | None = None


class CaseStatusResponseDTO(BaseModel):
    id: str
    name: str
    slug: str
    color: str
    order: int
    is_initial: bool
    is_final: bool
    pauses_sla: bool
    allowed_transitions: list[str]
    created_at: str

    class Config:
        from_attributes = True
