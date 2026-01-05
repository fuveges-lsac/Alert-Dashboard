from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

class AlertBase(BaseModel):
    source: str
    severity: str
    title: str
    message: Optional[str] = None
    host: Optional[str] = None
    tags: Dict[str, Any] = Field(default_factory=dict)

class AlertCreate(AlertBase):
    raw_data: Optional[Dict[str, Any]] = None

class AlertUpdate(BaseModel):
    status: Optional[str] = None
    ai_priority_score: Optional[int] = None
    ai_summary: Optional[str] = None

class AlertResponse(AlertBase):
    id: UUID
    ai_priority_score: Optional[int] = None
    ai_summary: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True

class AlertList(BaseModel):
    items: List[AlertResponse]
    total: int
    page: int
    page_size: int
