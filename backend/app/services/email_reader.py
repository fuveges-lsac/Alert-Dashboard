import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import re
import json
import structlog
import anthropic

from app.config import settings

logger = structlog.get_logger()


class EmailReader:
    def __init__(self):
        self.server = settings.IMAP_SERVER
        self.port = settings.IMAP_PORT
        self.username = settings.IMAP_USERNAME
        self.password = settings.IMAP_PASSWORD
        self.folder = settings.IMAP_FOLDER
        self.ai_client = None
        if settings.ANTHROPIC_API_KEY:
            self.ai_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def _connect(self) -> imaplib.IMAP4_SSL:
        """Connect to IMAP server."""
        mail = imaplib.IMAP4_SSL(self.server, self.port)
        mail.login(self.username, self.password)
        mail.select(self.folder)
        return mail

    def _decode_header_value(self, value: str) -> str:
        """Decode email header value."""
        if not value:
            return ""
        decoded_parts = decode_header(value)
        result = []
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(encoding or 'utf-8', errors='replace'))
            else:
                result.append(part)
        return ''.join(result)

    def _get_email_body(self, msg: email.message.Message) -> Dict[str, str]:
        """Extract text and HTML body from email."""
        text_body = ""
        html_body = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                if "attachment" in content_disposition:
                    continue

                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or 'utf-8'
                        decoded = payload.decode(charset, errors='replace')

                        if content_type == "text/plain":
                            text_body += decoded
                        elif content_type == "text/html":
                            html_body += decoded
                except Exception as e:
                    logger.warning("Failed to decode email part", error=str(e))
        else:
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or 'utf-8'
                    decoded = payload.decode(charset, errors='replace')
                    content_type = msg.get_content_type()

                    if content_type == "text/plain":
                        text_body = decoded
                    elif content_type == "text/html":
                        html_body = decoded
            except Exception as e:
                logger.warning("Failed to decode email body", error=str(e))

        return {"text": text_body, "html": html_body}

    def _strip_html(self, html: str) -> str:
        """Basic HTML to text conversion."""
        # Remove script and style elements
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        # Replace common elements
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<p[^>]*>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<div[^>]*>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</div>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<tr[^>]*>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<td[^>]*>', ' | ', text, flags=re.IGNORECASE)
        text = re.sub(r'<th[^>]*>', ' | ', text, flags=re.IGNORECASE)
        # Remove all remaining tags
        text = re.sub(r'<[^>]+>', '', text)
        # Decode HTML entities
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&lt;', '<', text)
        text = re.sub(r'&gt;', '>', text)
        text = re.sub(r'&quot;', '"', text)
        # Clean up whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()

    def _parse_with_ai(self, subject: str, body: str, sender: str) -> Dict[str, Any]:
        """Use Claude AI to parse email and extract alert information."""
        if not self.ai_client:
            # Fallback without AI
            return {
                "source": self._detect_source(sender, subject, body),
                "severity": self._detect_severity(subject, body),
                "title": subject[:200] if subject else "Email Alert",
                "message": body[:2000] if body else "",
                "host": self._extract_host(body),
                "is_alert": True
            }

        prompt = f"""Analyze this email and extract alert information. Return ONLY valid JSON.

From: {sender}
Subject: {subject}

Body:
{body[:3000]}

Extract and return JSON with these fields:
{{
    "is_alert": true/false (is this a monitoring/system alert or just regular email?),
    "source": "detected source system (e.g., Defender, vCenter, SolarWinds, Zabbix, ADAudit, custom, unknown)",
    "severity": "critical/high/medium/low/info (based on content urgency)",
    "title": "brief alert title (max 150 chars)",
    "message": "key details and context",
    "host": "affected hostname/IP if mentioned, or null",
    "suggested_actions": ["list of recommended actions if any"]
}}

Respond with ONLY the JSON object, no markdown or explanation."""

        try:
            response = self.ai_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            result = json.loads(response.content[0].text.strip())
            return result
        except Exception as e:
            logger.error("AI parsing failed", error=str(e))
            # Fallback
            return {
                "source": self._detect_source(sender, subject, body),
                "severity": self._detect_severity(subject, body),
                "title": subject[:200] if subject else "Email Alert",
                "message": body[:2000] if body else "",
                "host": self._extract_host(body),
                "is_alert": True
            }

    def _detect_source(self, sender: str, subject: str, body: str) -> str:
        """Detect alert source from email content."""
        content = f"{sender} {subject} {body}".lower()

        sources = {
            "defender": ["defender", "microsoft defender", "security center"],
            "vcenter": ["vcenter", "vsphere", "vmware", "esx"],
            "solarwinds": ["solarwinds", "orion"],
            "zabbix": ["zabbix"],
            "splunk": ["splunk"],
            "adaudit": ["adaudit", "active directory audit"],
            "nagios": ["nagios"],
            "prtg": ["prtg"],
            "datadog": ["datadog"],
        }

        for source, keywords in sources.items():
            if any(kw in content for kw in keywords):
                return source
        return "email"

    def _detect_severity(self, subject: str, body: str) -> str:
        """Detect severity from email content."""
        content = f"{subject} {body}".lower()

        if any(w in content for w in ["critical", "emergency", "fatal", "down", "failed", "failure", "outage"]):
            return "critical"
        elif any(w in content for w in ["high", "error", "alert", "warning", "degraded"]):
            return "high"
        elif any(w in content for w in ["medium", "notice", "attention"]):
            return "medium"
        elif any(w in content for w in ["low", "info", "informational"]):
            return "low"
        return "medium"

    def _extract_host(self, body: str) -> Optional[str]:
        """Try to extract hostname or IP from body."""
        # Look for IP addresses
        ip_match = re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', body)
        if ip_match:
            return ip_match.group()

        # Look for hostname patterns
        host_patterns = [
            r'host[:\s]+([a-zA-Z0-9\-_.]+)',
            r'server[:\s]+([a-zA-Z0-9\-_.]+)',
            r'machine[:\s]+([a-zA-Z0-9\-_.]+)',
        ]
        for pattern in host_patterns:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def fetch_unread_emails(self) -> List[Dict[str, Any]]:
        """Fetch all unread emails and parse them."""
        emails = []

        try:
            mail = self._connect()

            # Search for unread emails
            status, messages = mail.search(None, 'UNSEEN')
            if status != 'OK':
                logger.warning("Failed to search emails")
                return emails

            email_ids = messages[0].split()
            logger.info(f"Found {len(email_ids)} unread emails")

            for email_id in email_ids:
                try:
                    # Fetch the email
                    status, msg_data = mail.fetch(email_id, '(RFC822)')
                    if status != 'OK':
                        continue

                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    # Extract headers
                    subject = self._decode_header_value(msg.get('Subject', ''))
                    sender = self._decode_header_value(msg.get('From', ''))
                    date_str = msg.get('Date', '')
                    message_id = msg.get('Message-ID', '')

                    # Parse date
                    try:
                        date = parsedate_to_datetime(date_str)
                    except:
                        date = datetime.now(timezone.utc)

                    # Get body
                    body_parts = self._get_email_body(msg)
                    body = body_parts['text'] or self._strip_html(body_parts['html'])

                    # Parse with AI
                    parsed = self._parse_with_ai(subject, body, sender)

                    if parsed.get('is_alert', True):
                        emails.append({
                            "email_id": email_id.decode() if isinstance(email_id, bytes) else email_id,
                            "message_id": message_id,
                            "from": sender,
                            "subject": subject,
                            "date": date.isoformat(),
                            "source": parsed.get('source', 'email'),
                            "severity": parsed.get('severity', 'medium'),
                            "title": parsed.get('title', subject),
                            "message": parsed.get('message', body[:2000]),
                            "host": parsed.get('host'),
                            "raw_body": body[:5000],
                            "suggested_actions": parsed.get('suggested_actions', [])
                        })
                        logger.info("Parsed email alert", subject=subject, source=parsed.get('source'))
                    else:
                        logger.info("Email not an alert, skipping", subject=subject)

                except Exception as e:
                    logger.error("Failed to process email", email_id=email_id, error=str(e))

            mail.logout()

        except Exception as e:
            logger.error("Failed to fetch emails", error=str(e))

        return emails

    def mark_as_read(self, email_id: str) -> bool:
        """Mark an email as read."""
        try:
            mail = self._connect()
            mail.store(email_id.encode() if isinstance(email_id, str) else email_id, '+FLAGS', '\\Seen')
            mail.logout()
            return True
        except Exception as e:
            logger.error("Failed to mark email as read", email_id=email_id, error=str(e))
            return False


# Singleton
email_reader = EmailReader()
