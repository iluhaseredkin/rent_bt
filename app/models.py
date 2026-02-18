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
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_interaction = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Stat(Base):
    __tablename__ = "stats"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, index=True)
    action = Column(String)
    details = Column(String, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    city = Column(String, index=True)
    last_parsed_at = Column(DateTime, nullable=True)
    status = Column(String, default="active") # active, error, inactive
    error_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Suggestion(Base):
    __tablename__ = "suggestions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, index=True)
    type = Column(String) # channel, city, other
    content = Column(Text) # JSON or plain text
    status = Column(String, default="pending") # pending, approved, rejected
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(String)
