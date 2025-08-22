from sqlalchemy import Column, Integer, BigInteger, String, Enum, DECIMAL, DateTime, TIMESTAMP
# from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import declarative_base
import enum

Base = declarative_base()

# Enum for enrollment_status
class EnrollmentStatusEnum(str, enum.Enum):
    not_started = 'not_started'
    in_progress = 'in_progress'
    completed = 'completed'

class PatientEnrollment(Base):
    __tablename__ = "patient_enrollment"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pid = Column(BigInteger, unique=True, nullable=False)
    enrollment_status = Column(Enum(EnrollmentStatusEnum), default=EnrollmentStatusEnum.not_started)
    current_step = Column(String(50), default="Programs")
    progress_percentage = Column(DECIMAL(5, 2), default=0.00)
    total_programs = Column(Integer, default=0)
    completed_programs = Column(Integer, default=0)
    start_date = Column(DateTime, nullable=True)
    completion_date = Column(DateTime, nullable=True)
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)
    created_at = Column(TIMESTAMP, nullable=False)
    updated_at = Column(TIMESTAMP, nullable=False)
