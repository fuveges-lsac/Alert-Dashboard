from celery import Celery
from app.config import settings

celery_app = Celery("alert_intelligence", broker=settings.CELERY_BROKER_URL, backend=settings.CELERY_RESULT_BACKEND)
celery_app.conf.update(task_serializer="json", accept_content=["json"], result_serializer="json", timezone="UTC")

@celery_app.task
def process_new_alert(alert_id: str):
    from app.services.ai_scoring import score_alert_background
    import asyncio
    asyncio.run(score_alert_background(alert_id))
