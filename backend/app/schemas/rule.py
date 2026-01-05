from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel

class RuleBase(BaseModel):
    name: str
    description: Optional[str] = None
    rule_type: str
    conditions: List[Dict[str, Any]]
    actions: List[Dict[str, Any]]
    schedule: Optional[Dict[str, Any]] = None
    enabled: bool = True
    priority: int = 0

class RuleCreate(RuleBase):
    pass

class RuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    conditions: Optional[List[Dict[str, Any]]] = None
    actions: Optional[List[Dict[str, Any]]] = None
    enabled: Optional[bool] = None

class RuleResponse(RuleBase):
    id: UUID
    hit_count: int
    last_hit_at: Optional[datetime] = None
    created_at: datetime
    class Config:
        from_attributes = True
