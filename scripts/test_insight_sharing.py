"""Tests for structured report generation and non-blocking email delivery."""

import os
import unittest
from datetime import date
from unittest.mock import patch

import pandas as pd

from email_sender import send_report
from report_generator import generate_report


class FakeSMTP:
    sent_messages = []

    def __init__(self, _server, _port):
        self.logged_in = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def starttls(self):
        return None

    def login(self, _sender, _password):
        self.logged_in = True

    def send_message(self, message):
        self.sent_messages.append(message)


class FailingSMTP(FakeSMTP):
    def starttls(self):
        raise OSError("SMTP unavailable")


class TestInsightSharing(unittest.TestCase):
    def setUp(self):
        self.dataframe = pd.DataFrame(
            {"order_amount": [100.0, 40.0], "customer_id": [1, 2], "customer_segment": ["Enterprise", "SMB"]}
        )

    def test_report_contains_required_sections_and_computed_values(self):
        report = generate_report(self.dataframe, date(2026, 9, 7))
        self.assertIn("KPI SUMMARY", report)
        self.assertIn("KEY FINDING", report)
        self.assertIn("RECOMMENDED ACTION", report)
        self.assertIn("$140.00", report)
        self.assertIn("Enterprise", report)

    @patch.dict(os.environ, {"SENDER_EMAIL": "sender@example.com", "SENDER_PASSWORD": "app-password", "SMTP_PORT": "587"}, clear=True)
    def test_email_uses_environment_credentials(self):
        self.assertTrue(send_report("report", "recipient@example.com", FakeSMTP))
        self.assertEqual(FakeSMTP.sent_messages[-1]["From"], "sender@example.com")

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_credentials_skip_without_crashing(self):
        self.assertFalse(send_report("report", "recipient@example.com", FakeSMTP))

    @patch.dict(os.environ, {"SENDER_EMAIL": "sender@example.com", "SENDER_PASSWORD": "bad"}, clear=True)
    def test_smtp_failure_is_non_blocking(self):
        self.assertFalse(send_report("report", "recipient@example.com", FailingSMTP))


if __name__ == "__main__":
    unittest.main()