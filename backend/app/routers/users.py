from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User, ADGroupMapping
from app.schemas.user import UserResponse

router = APIRouter()

@router.get("", response_model=List[UserResponse])
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.is_active == True))
    return result.scalars().all()

@router.get("/ad-groups")
async def list_ad_group_mappings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ADGroupMapping))
    return result.scalars().all()

@router.post("/sync-ad")
async def sync_ad_users():
    return {"status": "sync_started"}
