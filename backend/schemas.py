from pydantic import BaseModel
from typing import List, Optional


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
    email: str = ""
    interests: List[str] = []
    notes: str = ""
    classification: str  # A, B, C, D
    badge_photo_url: Optional[str] = None
