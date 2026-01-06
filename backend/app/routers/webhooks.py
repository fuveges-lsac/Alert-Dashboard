from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.alert import Alert
from app.services.ai_scoring import score_alert_background
from app.config import settings

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


@router.post("/poll-emails")
async def poll_emails_now(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Manually trigger email inbox polling using Microsoft Graph API."""
    from app.services.graph_email_reader import graph_email_reader

    if not all([settings.AZURE_AD_TENANT_ID, settings.AZURE_AD_CLIENT_ID, settings.AZURE_AD_CLIENT_SECRET]):
        raise HTTPException(status_code=400, detail="Azure AD credentials not configured")

    try:
        emails = graph_email_reader.fetch_unread_emails()
        created_alerts = []

        for email_data in emails:
            alert = Alert(
                source=email_data.get("source", "email"),
                severity=email_data.get("severity", "medium"),
                title=email_data.get("title", email_data.get("subject", "Email Alert")),
                message=email_data.get("message", ""),
                host=email_data.get("host"),
                tags={
                    "email_from": email_data.get("from", ""),
                    "email_subject": email_data.get("subject", ""),
                    "email_date": email_data.get("date", ""),
                    "suggested_actions": email_data.get("suggested_actions", []),
                },
                raw_data={
                    "email_message_id": email_data.get("message_id"),
                    "raw_body": email_data.get("raw_body", ""),
                }
            )
            db.add(alert)
            await db.commit()
            await db.refresh(alert)
            created_alerts.append(str(alert.id))

            # Score with AI
            background_tasks.add_task(score_alert_background, str(alert.id))

        return {
            "status": "polled",
            "emails_found": len(emails),
            "alerts_created": created_alerts
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email polling failed: {str(e)}")


@router.get("/email-status")
async def email_connection_status():
    """Test Microsoft Graph API email connection."""
    from app.services.graph_email_reader import graph_email_reader
    return graph_email_reader.test_connection()
