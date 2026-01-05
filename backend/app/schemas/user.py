from typing import Optional, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel

class UserResponse(BaseModel):
    id: UUID
    email: str
    display_name: Optional[str] = None
    role: str
    ad_groups: List[str] = []
    last_login: Optional[datetime] = None
    is_active: bool
    class Config:
        from_attributes = True
