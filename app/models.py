from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, BigInteger, Text, Boolean
from .database import Base

class Listing(Base):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(BigInteger, index=True)
    channel_username = Column(String, index=True)
    date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Original data
    text = Column(Text)
    link = Column(String, unique=True)
    
    # Parsed data
    price_original = Column(Float, nullable=True)
    currency = Column(String, nullable=True)
    price_usd = Column(Float, index=True)
    city = Column(String, index=True) # Normalized city name

class User(Base):
    __tablename__ = "users"

    user_id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    
    # Preferences
    selected_city = Column(String, default="Batumi")
    min_price = Column(Integer, default=0)
    max_price = Column(Integer, default=5000)
    
    # Bot state
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_interaction = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Stat(Base):
    __tablename__ = "stats"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, index=True)
    action = Column(String)
    details = Column(String, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
