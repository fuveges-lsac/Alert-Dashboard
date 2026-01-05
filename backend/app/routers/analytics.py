from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.alert import Alert

router = APIRouter()

@router.get("/summary")
async def get_summary(db: AsyncSession = Depends(get_db)):
    status_query = select(Alert.status, func.count(Alert.id)).group_by(Alert.status)
    status_result = await db.execute(status_query)
    severity_query = select(Alert.severity, func.count(Alert.id)).where(Alert.status == "open").group_by(Alert.severity)
    severity_result = await db.execute(severity_query)
    return {"by_status": dict(status_result.all()), "by_severity": dict(severity_result.all())}

@router.get("/by-source")
async def get_by_source(db: AsyncSession = Depends(get_db)):
    query = select(Alert.source, func.count(Alert.id)).group_by(Alert.source).order_by(func.count(Alert.id).desc())
    result = await db.execute(query)
    return dict(result.all())
