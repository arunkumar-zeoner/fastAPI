from sqlalchemy import Column, BigInteger, String, Integer, Text, DateTime, TIMESTAMP, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class UserSecure(Base):
    __tablename__ = "users_secure"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(255), nullable=True)
    password = Column(String(255), nullable=True)
    last_update_password = Column(DateTime, nullable=True)
    last_update = Column(TIMESTAMP, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    password_history1 = Column(String(255), nullable=True)
    password_history2 = Column(String(255), nullable=True)
    password_history3 = Column(String(255), nullable=True)
    password_history4 = Column(String(255), nullable=True)
    last_challenge_response = Column(DateTime, nullable=True)
    login_work_area = Column(Text, nullable=True)
    login_fail_counter = Column(Integer, nullable=True, default=0)
    salt = Column(Text, nullable=True)
    forget_password_count = Column(Integer, nullable=True, default=0)
    otp_time = Column(DateTime, nullable=True, server_default=func.current_timestamp())
    current_session_id = Column(String(50), nullable=True)
