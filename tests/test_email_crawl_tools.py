from __future__ import annotations

import base64
import unittest
from typing import Any, Mapping

from life_admin.agent.tools.email_crawl import crawl_email_messages, get_email_message


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


class EmailCrawlToolsTest(unittest.TestCase):
    def test_crawl_google_messages_returns_source_items(self) -> None:
        body = base64.urlsafe_b64encode(b"Please send the budget by Friday.").decode("ascii").rstrip("=")
        http = FakeHttpClient(
            {
                "/users/me/messages?": {
                    "messages": [{"id": "gmail-1"}],
                    "nextPageToken": "next-google-page",
                },
                "/users/me/messages/gmail-1?": {
                    "id": "gmail-1",
                    "threadId": "thread-1",
                    "labelIds": ["INBOX", "IMPORTANT"],
                    "snippet": "Please send the budget",
                    "payload": {
                        "headers": [
                            {"name": "Subject", "value": "Budget request"},
                            {"name": "From", "value": "Ava Admin <ava@example.com>"},
                            {"name": "To", "value": "User <user@example.com>"},
                            {"name": "Date", "value": "Fri, 26 Jun 2026 10:30:00 +0000"},
                        ],
                        "mimeType": "text/plain",
                        "body": {"data": body},
                    },
                },
            }
        )

        result = crawl_email_messages(
            provider="google",
            access_token="token",
            query="newer_than:7d",
            max_results=10,
            http_client=http,
        )

        self.assertEqual(result["next_page_token"], "next-google-page")
        source_item = result["source_items"][0]
        self.assertEqual(source_item["provider"], "google")
        self.assertEqual(source_item["source_id"], "gmail-1")
        self.assertIn("Please send the budget by Friday.", source_item["content"])
        self.assertEqual(source_item["metadata"]["from"]["email"], "ava@example.com")
        self.assertIn("Authorization", http.headers[0])

    def test_get_outlook_message_returns_source_item_with_attachments(self) -> None:
        http = FakeHttpClient(
            {
                "/me/messages/outlook-1?": {
                    "id": "outlook-1",
                    "conversationId": "conversation-1",
                    "subject": "Prep for Monday",
                    "from": {"emailAddress": {"name": "Morgan", "address": "morgan@example.com"}},
                    "toRecipients": [{"emailAddress": {"name": "User", "address": "user@example.com"}}],
                    "ccRecipients": [],
                    "receivedDateTime": "2026-06-26T08:00:00Z",
                    "bodyPreview": "Please review the agenda.",
                    "body": {"contentType": "text", "content": "Please review the agenda before Monday."},
                    "hasAttachments": True,
                },
                "/attachments?": {
                    "value": [
                        {
                            "id": "attachment-1",
                            "name": "agenda.pdf",
                            "contentType": "application/pdf",
                            "size": 12345,
                        }
                    ]
                },
            }
        )

        result = get_email_message(
            provider="outlook",
            access_token="token",
            message_id="outlook-1",
            http_client=http,
        )

        source_item = result["source_item"]
        self.assertEqual(source_item["provider"], "outlook")
        self.assertEqual(source_item["source_id"], "outlook-1")
        self.assertIn("Please review the agenda before Monday.", source_item["content"])
        self.assertEqual(source_item["metadata"]["attachments"][0]["filename"], "agenda.pdf")


if __name__ == "__main__":
    unittest.main()
