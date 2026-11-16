from sqlalchemy import Column, Date, Float, Integer

from app.db.database import Base


class AnalyticsCache(Base):
    __tablename__ = "analytics_cache"

    date = Column(Date, primary_key=True, index=True)
    avg_freshness = Column(Float)
    high_risk_count = Column(Integer)
    total_scans = Column(Integer)
