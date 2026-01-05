import json
import anthropic
from app.config import settings

client = None
if settings.ANTHROPIC_API_KEY:
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

def score_alert(alert: dict) -> dict:
    if not client:
        return {"priority_score": 50, "summary": "AI scoring not configured", "suggested_actions": []}
    
    prompt = f"""Analyze this IT alert:
- Source: {alert.get('source')}
- Severity: {alert.get('severity')}
- Title: {alert.get('title')}
- Message: {alert.get('message')}
- Host: {alert.get('host')}

Return JSON: {{"priority_score": 0-100, "summary": "brief analysis", "suggested_actions": ["action1"]}}"""

    try:
        response = client.messages.create(model="claude-sonnet-4-20250514", max_tokens=500, messages=[{"role": "user", "content": prompt}])
        return json.loads(response.content[0].text.strip())
    except Exception as e:
        return {"priority_score": 50, "summary": f"Error: {e}", "suggested_actions": []}

async def score_alert_background(alert_id: str):
    from app.database import async_session_maker
    from app.models.alert import Alert
    from app.services.email_service import email_service
    from app.config import settings
    from sqlalchemy import select

    async with async_session_maker() as db:
        result = await db.execute(select(Alert).where(Alert.id == alert_id))
        alert = result.scalar_one_or_none()
        if alert:
            score_result = score_alert({"source": alert.source, "severity": alert.severity, "title": alert.title, "message": alert.message, "host": alert.host})
            alert.ai_priority_score = score_result.get("priority_score")
            alert.ai_summary = score_result.get("summary")
            await db.commit()

            # Send email notification for critical/high severity or high AI score
            should_notify = (
                alert.severity in ["critical", "high"] or
                (alert.ai_priority_score and alert.ai_priority_score >= 75)
            )

            if should_notify and settings.alert_notify_email_list:
                email_service.send_alert_notification(
                    to_emails=settings.alert_notify_email_list,
                    alert_id=str(alert.id),
                    severity=alert.severity,
                    title=alert.title,
                    message=alert.message or "",
                    host=alert.host,
                    ai_summary=alert.ai_summary,
                    ai_score=alert.ai_priority_score
                )
