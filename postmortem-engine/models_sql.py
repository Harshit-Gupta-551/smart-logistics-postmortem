from sqlalchemy import Column, Integer, String, Float, Text, DateTime, UniqueConstraint, Index
from sqlalchemy.sql import func
from db_sql import Base

class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False)

    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    duration_seconds = Column(Float, nullable=False, default=0.0)

    failure_detail = Column(String(2048), nullable=True)
    event_count = Column(Integer, nullable=False, default=0)

    raw_messages = Column(Text, nullable=False)   # JSON string
    source = Column(String(32), nullable=False, default="csv")

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("order_id", name="uq_incidents_order_id"),
        Index("ix_incidents_status", "status"),
    )

class Postmortem(Base):
    __tablename__ = "postmortems"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(64), nullable=False)
    model_name = Column(String(128), nullable=False)

    report_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("order_id", "model_name", name="uq_pm_order_model"),
        Index("ix_pm_order_id", "order_id"),
    )