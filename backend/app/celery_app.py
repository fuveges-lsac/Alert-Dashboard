from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery("alert_intelligence", broker=settings.CELERY_BROKER_URL, backend=settings.CELERY_RESULT_BACKEND)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    beat_schedule={
        "poll-email-inbox": {
            "task": "app.celery_app.poll_email_inbox",
            "schedule": settings.EMAIL_POLL_INTERVAL,  # seconds
        },
    },
)


@celery_app.task
def process_new_alert(alert_id: str):
    from app.services.ai_scoring import score_alert_background
    import asyncio
    asyncio.run(score_alert_background(alert_id))


@celery_app.task
def poll_email_inbox():
    """Poll inbox for new emails and create alerts."""
    import asyncio
    asyncio.run(_poll_emails_async())


async def _poll_emails_async():
    """Async function to poll emails and create alerts using Microsoft Graph API."""
    from app.services.graph_email_reader import graph_email_reader
    from app.database import async_session_maker
    from app.models.alert import Alert
    from app.services.ai_scoring import score_alert_background
    import structlog

    logger = structlog.get_logger()

    if not all([settings.AZURE_AD_TENANT_ID, settings.AZURE_AD_CLIENT_ID, settings.AZURE_AD_CLIENT_SECRET]):
        logger.warning("Azure AD credentials not configured, skipping email poll")
        return

    try:
        emails = graph_email_reader.fetch_unread_emails()
        logger.info(f"Polled inbox, found {len(emails)} alert emails")

        async with async_session_maker() as db:
            for email_data in emails:
                # Create alert from email
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

                logger.info("Created alert from email",
                           alert_id=str(alert.id),
                           source=alert.source,
                           severity=alert.severity)

                # Score with AI in background
                await score_alert_background(str(alert.id))

    except Exception as e:
        logger.error("Email polling failed", error=str(e))
