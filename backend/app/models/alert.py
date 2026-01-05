from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
from app.database import Base

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    ai_priority_score = Column(Integer, index=True)
    title = Column(String(500), nullable=False)
    message = Column(Text)
    host = Column(String(255), index=True)
    tags = Column(JSONB, default={})
    ai_summary = Column(Text)
    status = Column(String(20), default="open", index=True)
    acknowledged_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    acknowledged_at = Column(DateTime)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    resolved_at = Column(DateTime)
    suppressed_by_rule = Column(UUID(as_uuid=True), ForeignKey("rules.id"))
    raw_data = Column(JSONB)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
