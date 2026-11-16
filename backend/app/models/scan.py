from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.db.database import Base


class Scan(Base):
    __tablename__ = "scans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    fruit_type = Column(String, index=True)
    freshness_stage = Column(String)
    freshness_score = Column(Integer)
    shelf_life_hours = Column(Float)
    temperature = Column(Float)
    humidity = Column(Float)
    confidence = Column(Float)
    rot_probability = Column(Float)
    storage_type = Column(String(16))
    fruit_source = Column(String(16))
    thumbnail = Column(Text)
    heatmap = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
