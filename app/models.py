from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base

ROLE_ADMIN = "admin"
ROLE_VIEWER = "viewer"
VALID_ROLES = {ROLE_ADMIN, ROLE_VIEWER}


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default=ROLE_VIEWER)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


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

    # Always-present fields (100% fill rate in source form)
    incident_date = Column(Date, nullable=False)
    incident_time = Column(String)
    store_location = Column(String, nullable=False)
    incident_type = Column(String, nullable=False)  # Customer / Employee Incident
    recordable = Column(Boolean, nullable=False)
    reporter = Column(String)
    reporter_position = Column(String)
    summary = Column(String)

    # Injury subgroup (~70% fill rate)
    body_part = Column(String)
    body_side = Column(String)
    injury_cause = Column(String)

    # People involved
    customer_name = Column(String)
    employee_name = Column(String)

    # Statements / documentation (used for compliance metrics)
    customer_statement = Column(String)  # Yes / No
    employee_statement = Column(String)  # Yes / No
    video_available = Column(String)  # Yes / No
    drug_screen = Column(String)  # Yes / No
    photos_info = Column(String)  # free-text count
    witnesses_info = Column(String)  # free-text count

    upload = relationship("Upload", back_populates="incidents")
