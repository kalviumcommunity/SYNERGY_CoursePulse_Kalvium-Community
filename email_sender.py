"""Environment-configured, non-blocking SMTP report delivery."""

from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Callable


LOGGER = logging.getLogger(__name__)


def send_report(
    report_text: str,
    recipient: str,
    smtp_factory: Callable[..., smtplib.SMTP] = smtplib.SMTP,
) -> bool:
    """Send a report using environment credentials; return False on any delivery failure."""
    sender = os.environ.get("SENDER_EMAIL")
    password = os.environ.get("SENDER_PASSWORD")
    smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    if not sender or not password:
        LOGGER.warning("Email not configured; report delivery skipped.")
        return False
    if not recipient or "@" not in recipient:
        LOGGER.warning("Invalid recipient; report delivery skipped.")
        return False

    message = EmailMessage()
    message["Subject"] = "Weekly Analytics Report"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(report_text)
    try:
        with smtp_factory(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(message)
        LOGGER.info("Analytics report sent to %s", recipient)
        return True
    except Exception:
        LOGGER.exception("Report email failed; dashboard remains available.")
        return False