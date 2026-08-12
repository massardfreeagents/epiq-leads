from pydantic import BaseModel, field_validator
from typing import List, Optional
import re

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EmployeeOut(BaseModel):
    id: int
    name: str
    email: str
    phone: str
    photo_url: Optional[str] = None

    class Config:
        from_attributes = True


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class LeadCreate(BaseModel):
    employee_id: int
    first_name: str
    last_name: str = ""
    company: str = ""
    position: str = ""
    phone: str = ""
    emails: List[str] = []
    interests: List[str] = []
    notes: str = ""
    classification: str  # A, B, C, D
    badge_photo_url: Optional[str] = None

    @field_validator("emails")
    @classmethod
    def validate_emails(cls, v):
        for e in v:
            if e and not EMAIL_REGEX.match(e):
                raise ValueError(f"Email em formato inválido: {e}")
        return v
