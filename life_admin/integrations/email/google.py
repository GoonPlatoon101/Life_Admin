from __future__ import annotations

import base64
from typing import Any, Mapping
from urllib.parse import urlencode

from life_admin.integrations.email.http import UrlLibHttpClient
from life_admin.integrations.email.parsing import parse_addresses, parse_email_datetime, parse_first_address
from life_admin.integrations.email.types import (
    EmailAttachmentMetadata,
    EmailMessage,
    EmailPage,
    EmailProvider,
    EmailSearchQuery,
    HttpClient,
)


GMAIL_API_BASE_URL = "https://gmail.googleapis.com/gmail/v1"


class GoogleEmailCrawler:
    def __init__(self, access_token: str, http_client: HttpClient | None = None) -> None:
        self.access_token = access_token
        self.http_client = http_client or UrlLibHttpClient()

    def list_messages(self, search: EmailSearchQuery) -> EmailPage:
        params = {"maxResults": max(1, min(search.max_results, 100))}
        if search.query:
            params["q"] = search.query
        if search.page_token:
            params["pageToken"] = search.page_token

        listing = self.http_client.get_json(
            f"{GMAIL_API_BASE_URL}/users/me/messages?{urlencode(params)}",
            headers=self._headers(),
        )
        messages = tuple(
            self.get_message(str(item["id"]))
            for item in listing.get("messages", [])
            if isinstance(item, Mapping) and item.get("id")
        )
        return EmailPage(messages=messages, next_page_token=_optional_str(listing.get("nextPageToken")))

    def get_message(self, message_id: str) -> EmailMessage:
        params = urlencode({"format": "full"})
        data = self.http_client.get_json(
            f"{GMAIL_API_BASE_URL}/users/me/messages/{message_id}?{params}",
            headers=self._headers(),
        )
        return _normalize_gmail_message(data)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}", "Accept": "application/json"}


def _normalize_gmail_message(data: Mapping[str, Any]) -> EmailMessage:
    payload = _mapping(data.get("payload"))
    headers = _gmail_headers(payload)
    plain_text, html, attachments = _extract_gmail_parts(payload)

    return EmailMessage(
        provider=EmailProvider.GOOGLE,
        provider_message_id=str(data.get("id", "")),
        thread_id=_optional_str(data.get("threadId")),
        subject=headers.get("subject") or "(no subject)",
        sender=parse_first_address(headers.get("from")),
        recipients=parse_addresses(headers.get("to")),
        cc=parse_addresses(headers.get("cc")),
        received_at=parse_email_datetime(headers.get("date")),
        snippet=_optional_str(data.get("snippet")),
        plain_text=plain_text,
        html=html,
        labels=tuple(str(label) for label in data.get("labelIds", []) if label),
        attachments=attachments,
        raw=data,
    )


def _gmail_headers(payload: Mapping[str, Any]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for item in payload.get("headers", []):
        if isinstance(item, Mapping) and item.get("name"):
            headers[str(item["name"]).lower()] = str(item.get("value", ""))
    return headers


def _extract_gmail_parts(payload: Mapping[str, Any]) -> tuple[str | None, str | None, tuple[EmailAttachmentMetadata, ...]]:
    text_parts: list[str] = []
    html_parts: list[str] = []
    attachments: list[EmailAttachmentMetadata] = []

    def visit(part: Mapping[str, Any]) -> None:
        mime_type = _optional_str(part.get("mimeType"))
        filename = _optional_str(part.get("filename"))
        body = _mapping(part.get("body"))

        if filename:
            attachments.append(
                EmailAttachmentMetadata(
                    id=_optional_str(body.get("attachmentId")),
                    filename=filename,
                    mime_type=mime_type,
                    size=_optional_int(body.get("size")),
                )
            )

        decoded = _decode_gmail_body(_optional_str(body.get("data")))
        if decoded and mime_type == "text/plain":
            text_parts.append(decoded)
        elif decoded and mime_type == "text/html":
            html_parts.append(decoded)

        for child in part.get("parts", []):
            if isinstance(child, Mapping):
                visit(child)

    visit(payload)
    return (
        "\n\n".join(text_parts) or None,
        "\n\n".join(html_parts) or None,
        tuple(attachments),
    )


def _decode_gmail_body(data: str | None) -> str | None:
    if not data:
        return None
    padded = data + "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
    except ValueError:
        return None


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _optional_str(value: Any) -> str | None:
    return str(value) if value is not None else None


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

