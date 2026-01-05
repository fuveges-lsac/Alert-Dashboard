import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
import structlog

from app.config import settings

logger = structlog.get_logger()


class EmailService:
    def __init__(self):
        self.server = settings.SMTP_SERVER
        self.port = settings.SMTP_PORT
        self.username = settings.SMTP_USERNAME
        self.password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM_EMAIL

    def _create_connection(self):
        """Create SMTP connection with TLS."""
        context = ssl.create_default_context()
        server = smtplib.SMTP(self.server, self.port)
        server.starttls(context=context)
        if self.username and self.password:
            server.login(self.username, self.password)
        return server

    def send_email(
        self,
        to_emails: List[str],
        subject: str,
        body_html: str,
        body_text: Optional[str] = None
    ) -> bool:
        """Send an email to one or more recipients."""
        if not to_emails:
            logger.warning("No recipients specified for email")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_email
            msg["To"] = ", ".join(to_emails)

            if body_text:
                msg.attach(MIMEText(body_text, "plain"))
            msg.attach(MIMEText(body_html, "html"))

            with self._create_connection() as server:
                server.sendmail(self.from_email, to_emails, msg.as_string())

            logger.info("Email sent successfully", to=to_emails, subject=subject)
            return True

        except Exception as e:
            logger.error("Failed to send email", error=str(e), to=to_emails)
            return False

    def send_alert_notification(
        self,
        to_emails: List[str],
        alert_id: str,
        severity: str,
        title: str,
        message: str,
        host: Optional[str] = None,
        ai_summary: Optional[str] = None,
        ai_score: Optional[int] = None
    ) -> bool:
        """Send an alert notification email."""
        severity_colors = {
            "critical": "#ff4757",
            "high": "#ff9f43",
            "medium": "#feca57",
            "low": "#26de81"
        }
        color = severity_colors.get(severity.lower(), "#8b949e")

        subject = f"[{severity.upper()}] Alert: {title}"

        body_html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, sans-serif; background: #0a0e14; color: #e6edf3; padding: 20px; }}
        .container {{ max-width: 600px; margin: 0 auto; background: #151c28; border-radius: 10px; overflow: hidden; }}
        .header {{ background: {color}; padding: 20px; color: white; }}
        .header h1 {{ margin: 0; font-size: 18px; }}
        .content {{ padding: 20px; }}
        .field {{ margin-bottom: 15px; }}
        .label {{ color: #8b949e; font-size: 12px; text-transform: uppercase; margin-bottom: 5px; }}
        .value {{ color: #e6edf3; }}
        .ai-box {{ background: rgba(168,85,247,0.1); border: 1px solid rgba(168,85,247,0.3); border-radius: 6px; padding: 15px; margin-top: 15px; }}
        .ai-label {{ color: #a855f7; font-weight: bold; margin-bottom: 5px; }}
        .score {{ font-size: 24px; font-weight: bold; color: {color}; }}
        .footer {{ padding: 15px 20px; border-top: 1px solid #30363d; font-size: 12px; color: #8b949e; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔺 {severity.upper()} ALERT</h1>
        </div>
        <div class="content">
            <div class="field">
                <div class="label">Title</div>
                <div class="value" style="font-size: 16px; font-weight: bold;">{title}</div>
            </div>
            <div class="field">
                <div class="label">Message</div>
                <div class="value">{message or 'No message provided'}</div>
            </div>
            {f'<div class="field"><div class="label">Host</div><div class="value">{host}</div></div>' if host else ''}
            <div class="field">
                <div class="label">Alert ID</div>
                <div class="value" style="font-family: monospace;">{alert_id}</div>
            </div>
            {f'''
            <div class="ai-box">
                <div class="ai-label">🤖 AI Analysis</div>
                {f'<div class="score">Priority Score: {ai_score}/100</div>' if ai_score else ''}
                {f'<div class="value" style="margin-top: 10px;">{ai_summary}</div>' if ai_summary else ''}
            </div>
            ''' if ai_summary or ai_score else ''}
        </div>
        <div class="footer">
            Alert Intelligence Dashboard • LSAC
        </div>
    </div>
</body>
</html>
"""

        body_text = f"""
[{severity.upper()}] ALERT: {title}

Message: {message or 'No message provided'}
Host: {host or 'N/A'}
Alert ID: {alert_id}
{f'AI Score: {ai_score}/100' if ai_score else ''}
{f'AI Summary: {ai_summary}' if ai_summary else ''}

--
Alert Intelligence Dashboard • LSAC
"""

        return self.send_email(to_emails, subject, body_html, body_text)


# Singleton instance
email_service = EmailService()
