from sqlalchemy import (
    Column, String, Integer, Float, Text, SmallInteger, TIMESTAMP
)
# from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class ListOptions(Base):
    __tablename__ = "list_options"

    list_id = Column(String(100), primary_key=True)
    option_id = Column(String(100), primary_key=True)
    title = Column(String(255), nullable=False)
    seq = Column(Integer, nullable=False, default=0)
    is_default = Column(SmallInteger, nullable=False, default=0)
    option_value = Column(Float, nullable=False, default=0.0)
    mapping = Column(String(31), nullable=False, default="")
    notes = Column(Text, nullable=True)
    codes = Column(String(255), nullable=False, default="")
    toggle_setting_1 = Column(SmallInteger, nullable=False, default=0)
    toggle_setting_2 = Column(SmallInteger, nullable=False, default=0)
    activity = Column(SmallInteger, nullable=False, default=1)
    subtype = Column(String(31), nullable=False, default="")
    edit_options = Column(SmallInteger, nullable=False, default=1)
    timestamp = Column(TIMESTAMP, nullable=False, server_default=func.current_timestamp())
