from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from pydantic import BaseModel, EmailStr
from app.database import get_db
from app.models.alert import Alert
from app.schemas.alert import AlertResponse, AlertList
from app.services.email_service import email_service

router = APIRouter()


class TestEmailRequest(BaseModel):
    to_email: str


class NotifyRequest(BaseModel):
    emails: List[str]

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


@router.post("/{alert_id}/notify")
async def notify_alert(alert_id: UUID, request: NotifyRequest, db: AsyncSession = Depends(get_db)):
    """Send email notification for a specific alert."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    success = email_service.send_alert_notification(
        to_emails=request.emails,
        alert_id=str(alert.id),
        severity=alert.severity,
        title=alert.title,
        message=alert.message or "",
        host=alert.host,
        ai_summary=alert.ai_summary,
        ai_score=alert.ai_priority_score
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to send email notification")

    return {"status": "sent", "recipients": request.emails}


@router.post("/test-email")
async def test_email(request: TestEmailRequest):
    """Send a test email to verify SMTP configuration."""
    success = email_service.send_email(
        to_emails=[request.to_email],
        subject="[Test] Alert Intelligence - Email Configuration Test",
        body_html="""
        <html>
        <body style="font-family: sans-serif; background: #0a0e14; color: #e6edf3; padding: 20px;">
            <div style="max-width: 500px; margin: 0 auto; background: #151c28; border-radius: 10px; padding: 20px;">
                <h2 style="color: #3b82f6;">✅ Email Configuration Working!</h2>
                <p>Your SMTP2GO email settings are configured correctly.</p>
                <p style="color: #8b949e; font-size: 12px;">Alert Intelligence Dashboard • LSAC</p>
            </div>
        </body>
        </html>
        """,
        body_text="Email Configuration Test - Your SMTP settings are working correctly!"
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to send test email")

    return {"status": "sent", "to": request.to_email}
