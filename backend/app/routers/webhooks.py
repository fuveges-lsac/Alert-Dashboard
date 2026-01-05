from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.alert import Alert
from app.services.ai_scoring import score_alert_background

router = APIRouter()

@router.post("/zabbix")
async def zabbix_webhook(payload: dict, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    alert = Alert(source="zabbix", severity=payload.get("severity", "medium"), title=payload.get("subject", "Zabbix Alert"), message=payload.get("message"), host=payload.get("host"), raw_data=payload)
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    background_tasks.add_task(score_alert_background, str(alert.id))
    return {"status": "received", "alert_id": str(alert.id)}

@router.post("/splunk")
async def splunk_webhook(payload: dict, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    alert = Alert(source="splunk", severity=payload.get("severity", "medium"), title=payload.get("search_name", "Splunk Alert"), message=payload.get("result", {}).get("_raw"), host=payload.get("result", {}).get("host"), raw_data=payload)
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    background_tasks.add_task(score_alert_background, str(alert.id))
    return {"status": "received", "alert_id": str(alert.id)}

@router.post("/generic")
async def generic_webhook(payload: dict, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    alert = Alert(source=payload.get("source", "generic"), severity=payload.get("severity", "medium"), title=payload.get("title", "Alert"), message=payload.get("message"), host=payload.get("host"), tags=payload.get("tags", {}), raw_data=payload)
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    background_tasks.add_task(score_alert_background, str(alert.id))
    return {"status": "received", "alert_id": str(alert.id)}
