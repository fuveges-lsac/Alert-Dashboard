from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
from app.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    display_name = Column(String(255))
    ad_object_id = Column(String(255), unique=True, index=True)
    role = Column(String(50), default="readonly")
    ad_groups = Column(JSONB, default=[])
    last_login = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class ADGroupMapping(Base):
    __tablename__ = "ad_group_mappings"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ad_group_name = Column(String(255), nullable=False)
    ad_group_id = Column(String(255))
    app_role = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
