from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    phone = Column(String, nullable=False)  # E.164, ex: 5521972909065
    photo_url = Column(String, nullable=True)
    sender_verified = Column(String, default="pending")  # pending / verified
    created_at = Column(DateTime, default=datetime.utcnow)

    leads = relationship("Lead", back_populates="employee")


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)

    first_name = Column(String)
    last_name = Column(String)
    company = Column(String)
    position = Column(String)
    phone = Column(String)
    email = Column(String)

    interests = Column(JSON, default=list)  # lista de strings marcadas
    notes = Column(Text, default="")  # texto livre (digitado ou transcrito)
    classification = Column(String)  # "A", "B", "C" ou "D"

    badge_photo_url = Column(String, nullable=True)
    email_sent = Column(String, default="pending")  # pending / sent / failed
    whatsapp_sent = Column(String, default="pending")

    created_at = Column(DateTime, default=datetime.utcnow)

    employee = relationship("Employee", back_populates="leads")
