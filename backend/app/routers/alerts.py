from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.database import get_db
from app.models.alert import Alert
from app.schemas.alert import AlertResponse, AlertList

router = APIRouter()

@router.get("", response_model=AlertList)
async def list_alerts(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    source: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(Alert)
    if status:
        query = query.where(Alert.status == status)
    if severity:
        query = query.where(Alert.severity == severity)
    if source:
        query = query.where(Alert.source == source)
    
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)
    
    query = query.order_by(desc(Alert.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    
    return AlertList(items=result.scalars().all(), total=total or 0, page=page, page_size=page_size)

@router.get("/priority-queue", response_model=List[AlertResponse])
async def get_priority_queue(limit: int = Query(10, ge=1, le=50), db: AsyncSession = Depends(get_db)):
    query = select(Alert).where(Alert.status == "open").where(Alert.ai_priority_score.isnot(None)).order_by(desc(Alert.ai_priority_score)).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert

@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(alert_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = "acknowledged"
    await db.commit()
    await db.refresh(alert)
    return alert

@router.post("/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(alert_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = "resolved"
    await db.commit()
    await db.refresh(alert)
    return alert
