from sqlalchemy import (
    Column, Integer, String, DateTime, Enum, SmallInteger, TIMESTAMP
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class EnrollmentPrograms(Base):
    __tablename__ = "enrollment_programs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    enrollment_id = Column(Integer, nullable=False, index=True)
    program_option_id = Column(String(50), nullable=False, index=True)
    program_name = Column(String(255), nullable=False)
    program_status = Column(
        Enum(
            'selected','consent_pending','consent_done','device_pending','device_done',
            'education_pending','education_done','care_plan_pending','care_plan_done','completed',
            name='program_status_enum'
        ),
        nullable=True,
        default='selected',
        index=True
    )
    consent_document_id = Column(Integer, nullable=True)
    device_completed_date = Column(DateTime, nullable=True)
    training_completed = Column(SmallInteger, nullable=True, default=0)
    patient_education_given = Column(SmallInteger, nullable=True, default=0)
    education_completed_date = Column(DateTime, nullable=True)
    care_plan_document_id = Column(Integer, nullable=True)
    completed_date = Column(DateTime, nullable=True)
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
