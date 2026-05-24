"""Database models and connection setup."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, BigInteger, ForeignKey
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
    last_change = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Outage(Base):
    """Model representing an internet outage event for statistics."""
    __tablename__ = 'outages'
    
    id = Column(Integer, primary_key=True, index=True)
    host_id = Column(Integer, ForeignKey('hosts.id'))
    offline_at = Column(DateTime(timezone=True))
    online_at = Column(DateTime(timezone=True), nullable=True)
