from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, EmailStr


class StudentBase(BaseModel):
    register_number: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    division: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None


class StudentCreate(StudentBase):
    pass


class StudentUpdate(BaseModel):
    register_number: Optional[str] = Field(None, min_length=1, max_length=100)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    division: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None


class StudentRead(StudentBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
