"""Database models and connection setup."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, BigInteger, ForeignKey, Time
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

from src.config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()

class Host(Base):
    """Model representing a network host to be monitored."""
    __tablename__ = 'hosts'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, index=True)
    address = Column(String, index=True)
    pretty_name = Column(String)
    is_active = Column(Boolean, default=True)
    status_up = Column(Boolean, default=None)
    ping_threshold = Column(Integer, nullable=True)
    last_change = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class ChatSettings(Base):
    """Model representing settings for a specific chat (e.g., quiet hours, reports)."""
    __tablename__ = 'chat_settings'
    
    chat_id = Column(BigInteger, primary_key=True, autoincrement=False)
    quiet_hours_start = Column(Time, nullable=True)
    quiet_hours_end = Column(Time, nullable=True)
    
    # Report settings
    report_enabled = Column(Boolean, default=True)
    from datetime import time
    report_time = Column(Time, default=time(21, 0))
    report_skip_empty_daily = Column(Boolean, default=False)
    timezone_name = Column(String, default="Europe/Kyiv")

class Outage(Base):
    """Model representing an internet outage event for statistics."""
    __tablename__ = 'outages'
    
    id = Column(Integer, primary_key=True, index=True)
    host_id = Column(Integer, ForeignKey('hosts.id'))
    offline_at = Column(DateTime(timezone=True))
    online_at = Column(DateTime(timezone=True), nullable=True)
