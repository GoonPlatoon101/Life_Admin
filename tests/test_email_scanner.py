from __future__ import annotations

import base64
import unittest
from typing import Any, Mapping

from life_admin.scanner import EmailScanRequest, scan_email_messages


class FakeHttpClient:
    def __init__(self, responses: Mapping[str, Mapping[str, Any]]) -> None:
        self.responses = responses
        self.urls: list[str] = []
        self.headers: list[Mapping[str, str] | None] = []

    def get_json(self, url: str, headers: Mapping[str, str] | None = None) -> Mapping[str, Any]:
        self.urls.append(url)
        self.headers.append(headers)
        for key, response in self.responses.items():
            if key in url:
                return response
        raise AssertionError(f"No fake response for {url}")


class EmailScannerTest(unittest.TestCase):
    def test_scan_email_messages_returns_normalized_source_items(self) -> None:
        body = base64.urlsafe_b64encode(b"Please confirm the investor sync agenda.").decode("ascii").rstrip("=")
        http = FakeHttpClient(
            {
                "/users/me/messages?": {
                    "messages": [{"id": "gmail-1"}],
                    "nextPageToken": "next-page",
                },
                "/users/me/messages/gmail-1?": {
                    "id": "gmail-1",
                    "threadId": "thread-1",
                    "snippet": "Please confirm",
                    "payload": {
                        "headers": [
                            {"name": "Subject", "value": "Investor sync agenda"},
                            {"name": "From", "value": "Maya <maya@example.com>"},
                            {"name": "Date", "value": "Fri, 26 Jun 2026 10:30:00 +0000"},
                        ],
                        "mimeType": "text/plain",
                        "body": {"data": body},
                    },
                },
            }
        )

        result = scan_email_messages(
            EmailScanRequest(
                provider="google",
                access_token="secret-token",
                query="newer_than:7d",
                max_results=5,
            ),
            http_client=http,
        )

        self.assertEqual(result["provider"], "google")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["next_page_token"], "next-page")
        source_item = result["source_items"][0]
        self.assertEqual(source_item["source_type"], "email")
        self.assertEqual(source_item["source_id"], "gmail-1")
        self.assertIn("Investor sync agenda", source_item["content"])
        self.assertIn("Please confirm the investor sync agenda.", source_item["content"])
        self.assertIn("Authorization", http.headers[0])


if __name__ == "__main__":
    unittest.main()
