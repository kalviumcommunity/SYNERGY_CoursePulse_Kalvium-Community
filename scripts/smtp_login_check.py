"""Login-only SMTP check for the .env credentials (no mail is sent)."""
import logging
import os
import smtplib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import email_sender  # noqa: E402  (import triggers the .env loader)

sender = os.environ.get("SENDER_EMAIL", "")
password = os.environ.get("SENDER_PASSWORD", "")
server = os.environ.get("SMTP_SERVER", "")
port = os.environ.get("SMTP_PORT", "")

print("env now set?  SENDER_EMAIL:", bool(sender), "| SENDER_PASSWORD:", bool(password))
print("SMTP_SERVER:", server, "| SMTP_PORT:", port)
print("sender looks like an email?", "@" in sender,
      "| placeholder still present?", "your-" in sender or "example.com" in sender)
print("password placeholder still present?", "your-" in password.lower(),
      "| password length:", len(password))

print("starting REAL login-only SMTP test (no mail sent)...")
try:
    with smtplib.SMTP(server, int(port), timeout=25) as smtp:
        smtp.starttls()
        smtp.login(sender, password)
    print("SMTP LOGIN: SUCCESS - credentials are valid")
except smtplib.SMTPAuthenticationError as exc:
    print("SMTP LOGIN: AUTH FAILED ->", exc.smtp_code, exc.smtp_error)
except Exception as exc:  # noqa: BLE001 - report any transport failure type
    print("SMTP LOGIN: FAILED ->", type(exc).__name__, str(exc)[:200])