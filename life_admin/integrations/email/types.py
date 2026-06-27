from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Mapping, Protocol


class EmailProvider(StrEnum):
    GOOGLE = "google"
    OUTLOOK = "outlook"


@dataclass(frozen=True)
class EmailAddress:
    name: str | None
    email: str


@dataclass(frozen=True)
class EmailAttachmentMetadata:
    id: str | None
    filename: str
    mime_type: str | None = None
    size: int | None = None


@dataclass(frozen=True)
class EmailMessage:
    provider: EmailProvider
    provider_message_id: str
    thread_id: str | None
    subject: str
    sender: EmailAddress | None
    recipients: tuple[EmailAddress, ...]
    cc: tuple[EmailAddress, ...]
    received_at: datetime | None
    snippet: str | None
    plain_text: str | None
    html: str | None
    labels: tuple[str, ...] = ()
    attachments: tuple[EmailAttachmentMetadata, ...] = ()
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def to_source_item(self) -> dict[str, Any]:
        """Return the normalized item shape consumed by the agent loop."""
        content_parts = [self.subject, self.snippet, self.plain_text]
        content = "\n\n".join(part for part in content_parts if part)
        return {
            "source_type": "email",
            "provider": self.provider.value,
            "source_id": self.provider_message_id,
            "thread_id": self.thread_id,
            "title": self.subject,
            "content": content,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "metadata": {
                "from": _address_to_dict(self.sender),
                "to": [_address_to_dict(address) for address in self.recipients],
                "cc": [_address_to_dict(address) for address in self.cc],
                "labels": list(self.labels),
                "attachments": [
                    {
                        "id": attachment.id,
                        "filename": attachment.filename,
                        "mime_type": attachment.mime_type,
                        "size": attachment.size,
                    }
                    for attachment in self.attachments
                ],
            },
        }


@dataclass(frozen=True)
class EmailSearchQuery:
    query: str | None = None
    max_results: int = 25
    page_token: str | None = None


@dataclass(frozen=True)
class EmailPage:
    messages: tuple[EmailMessage, ...]
    next_page_token: str | None = None


class EmailCrawler(Protocol):
    def list_messages(self, search: EmailSearchQuery) -> EmailPage:
        """List normalized email messages from a provider."""

    def get_message(self, message_id: str) -> EmailMessage:
        """Fetch one normalized email message by provider id."""


class HttpClient(Protocol):
    def get_json(self, url: str, headers: Mapping[str, str] | None = None) -> Mapping[str, Any]:
        """Return decoded JSON from a GET request."""


def _address_to_dict(address: EmailAddress | None) -> dict[str, str | None] | None:
    if address is None:
        return None
    return {"name": address.name, "email": address.email}

