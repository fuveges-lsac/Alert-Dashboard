import httpx
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import re
import structlog
import anthropic

from app.config import settings

logger = structlog.get_logger()


class GraphEmailReader:
    """Read emails using Microsoft Graph API."""

    def __init__(self):
        self.tenant_id = settings.AZURE_AD_TENANT_ID
        self.client_id = settings.AZURE_AD_CLIENT_ID
        self.client_secret = settings.AZURE_AD_CLIENT_SECRET
        self.mailbox = settings.IMAP_USERNAME  # Reuse this for the mailbox address
        self.access_token = None
        self.ai_client = None
        if settings.ANTHROPIC_API_KEY:
            self.ai_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def _get_access_token(self) -> Optional[str]:
        """Get OAuth2 access token using client credentials flow."""
        if not all([self.tenant_id, self.client_id, self.client_secret]):
            logger.error("Azure AD credentials not configured")
            return None

        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"

        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials"
        }

        try:
            with httpx.Client() as client:
                response = client.post(token_url, data=data)
                response.raise_for_status()
                token_data = response.json()
                self.access_token = token_data.get("access_token")
                return self.access_token
        except Exception as e:
            logger.error("Failed to get access token", error=str(e))
            return None

    def _make_graph_request(self, endpoint: str, method: str = "GET", data: dict = None) -> Optional[dict]:
        """Make a request to Microsoft Graph API."""
        if not self.access_token:
            self.access_token = self._get_access_token()
            if not self.access_token:
                return None

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        url = f"https://graph.microsoft.com/v1.0{endpoint}"

        try:
            with httpx.Client() as client:
                if method == "GET":
                    response = client.get(url, headers=headers)
                elif method == "PATCH":
                    response = client.patch(url, headers=headers, json=data)
                elif method == "POST":
                    response = client.post(url, headers=headers, json=data)

                response.raise_for_status()
                return response.json() if response.content else {}
        except httpx.HTTPStatusError as e:
            logger.error("Graph API request failed", status=e.response.status_code, error=str(e))
            # Token might be expired, clear it
            if e.response.status_code == 401:
                self.access_token = None
            return None
        except Exception as e:
            logger.error("Graph API request error", error=str(e))
            return None

    def _strip_html(self, html: str) -> str:
        """Basic HTML to text conversion."""
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<p[^>]*>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<div[^>]*>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<tr[^>]*>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<td[^>]*>', ' | ', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&lt;', '<', text)
        text = re.sub(r'&gt;', '>', text)
        text = re.sub(r'&quot;', '"', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()

    def _parse_with_ai(self, subject: str, body: str, sender: str) -> Dict[str, Any]:
        """Use Claude AI to parse email and extract alert information."""
        if not self.ai_client:
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
        ip_match = re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', body)
        if ip_match:
            return ip_match.group()
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
        """Fetch unread emails from the mailbox."""
        emails = []

        if not self.mailbox:
            logger.warning("Mailbox not configured")
            return emails

        # Get unread messages from inbox
        endpoint = f"/users/{self.mailbox}/mailFolders/inbox/messages"
        params = "?$filter=isRead eq false&$top=50&$select=id,subject,from,receivedDateTime,body,bodyPreview"

        result = self._make_graph_request(endpoint + params)
        if not result:
            return emails

        messages = result.get("value", [])
        logger.info(f"Found {len(messages)} unread emails via Graph API")

        for msg in messages:
            try:
                message_id = msg.get("id")
                subject = msg.get("subject", "")
                sender = msg.get("from", {}).get("emailAddress", {}).get("address", "")
                date_str = msg.get("receivedDateTime", "")
                body_content = msg.get("body", {}).get("content", "")
                body_type = msg.get("body", {}).get("contentType", "text")

                # Convert HTML to text if needed
                if body_type.lower() == "html":
                    body = self._strip_html(body_content)
                else:
                    body = body_content

                # Parse with AI
                parsed = self._parse_with_ai(subject, body, sender)

                if parsed.get("is_alert", True):
                    emails.append({
                        "email_id": message_id,
                        "message_id": message_id,
                        "from": sender,
                        "subject": subject,
                        "date": date_str,
                        "source": parsed.get("source", "email"),
                        "severity": parsed.get("severity", "medium"),
                        "title": parsed.get("title", subject),
                        "message": parsed.get("message", body[:2000]),
                        "host": parsed.get("host"),
                        "raw_body": body[:5000],
                        "suggested_actions": parsed.get("suggested_actions", [])
                    })

                    # Mark as read
                    self.mark_as_read(message_id)

                    logger.info("Parsed email alert via Graph", subject=subject, source=parsed.get("source"))
                else:
                    # Mark non-alerts as read too
                    self.mark_as_read(message_id)
                    logger.info("Email not an alert, skipping", subject=subject)

            except Exception as e:
                logger.error("Failed to process email", error=str(e))

        return emails

    def mark_as_read(self, message_id: str) -> bool:
        """Mark an email as read."""
        if not self.mailbox:
            return False

        endpoint = f"/users/{self.mailbox}/messages/{message_id}"
        result = self._make_graph_request(endpoint, method="PATCH", data={"isRead": True})
        return result is not None

    def test_connection(self) -> Dict[str, Any]:
        """Test the Graph API connection."""
        if not all([self.tenant_id, self.client_id, self.client_secret]):
            return {"success": False, "error": "Azure AD credentials not configured"}

        token = self._get_access_token()
        if not token:
            return {"success": False, "error": "Failed to get access token"}

        # Try to get mailbox info
        endpoint = f"/users/{self.mailbox}"
        result = self._make_graph_request(endpoint)

        if result:
            return {
                "success": True,
                "mailbox": self.mailbox,
                "display_name": result.get("displayName", ""),
                "mail": result.get("mail", "")
            }
        else:
            return {"success": False, "error": "Failed to access mailbox"}


# Singleton
graph_email_reader = GraphEmailReader()
