from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Upload(Base):
    __tablename__ = "uploads"

    id = Column(Integer, primary_key=True)
    filename = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    row_count = Column(Integer, default=0, nullable=False)

    incidents = relationship(
        "Incident", back_populates="upload", cascade="all, delete-orphan"
    )


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True)
    upload_id = Column(Integer, ForeignKey("uploads.id"), nullable=False)
    date = Column(Date, nullable=False)
    department = Column(String, nullable=False)
    incident_type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    description = Column(String)
    days_lost = Column(Float, default=0.0)
    status = Column(String)

    upload = relationship("Upload", back_populates="incidents")
