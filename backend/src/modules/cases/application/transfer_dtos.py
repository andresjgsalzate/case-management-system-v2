from pydantic import BaseModel, Field, field_validator


class TransferCaseDTO(BaseModel):
    to_user_id: str = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def reason_not_whitespace(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("reason must not be empty or whitespace only")
        return v.strip()


class TransferResponseDTO(BaseModel):
    id: str
    case_id: str
    from_user_id: str | None
    from_level: int
    to_user_id: str
    to_team_id: str
    to_level: int
    transfer_type: str
    reason: str
    created_at: str
