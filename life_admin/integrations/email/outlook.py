from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import quote, urlencode

from life_admin.integrations.email.http import UrlLibHttpClient
from life_admin.integrations.email.parsing import parse_iso_datetime
from life_admin.integrations.email.types import (
    EmailAddress,
    EmailAttachmentMetadata,
    EmailMessage,
    EmailPage,
    EmailProvider,
    EmailSearchQuery,
    HttpClient,
)


GRAPH_API_BASE_URL = "https://graph.microsoft.com/v1.0"


class OutlookEmailCrawler:
    def __init__(self, access_token: str, http_client: HttpClient | None = None) -> None:
        self.access_token = _normalize_access_token(access_token)
        self.http_client = http_client or UrlLibHttpClient()

    def list_messages(self, search: EmailSearchQuery) -> EmailPage:
        if search.page_token:
            data = self.http_client.get_json(search.page_token, headers=self._headers(search=bool(search.query)))
        else:
            params: dict[str, str | int] = {
                "$top": max(1, min(search.max_results, 50)),
                "$select": "id,conversationId,subject,from,toRecipients,ccRecipients,receivedDateTime,bodyPreview,body,hasAttachments",
            }
            if search.query:
                params["$search"] = f'"{search.query}"'
            else:
                params["$orderby"] = "receivedDateTime desc"

            data = self.http_client.get_json(
                f"{GRAPH_API_BASE_URL}/me/messages?{urlencode(params)}",
                headers=self._headers(search=bool(search.query)),
            )

        messages = tuple(
            _normalize_outlook_message(item)
            for item in data.get("value", [])
            if isinstance(item, Mapping)
        )
        return EmailPage(messages=messages, next_page_token=_optional_str(data.get("@odata.nextLink")))

    def get_message(self, message_id: str) -> EmailMessage:
        select = "id,conversationId,subject,from,toRecipients,ccRecipients,receivedDateTime,bodyPreview,body,hasAttachments"
        data = self.http_client.get_json(
            f"{GRAPH_API_BASE_URL}/me/messages/{quote(message_id)}?{urlencode({'$select': select})}",
            headers=self._headers(),
        )
        message = _normalize_outlook_message(data)
        if data.get("hasAttachments"):
            attachments = self._list_attachments(message_id)
            return EmailMessage(**{**message.__dict__, "attachments": attachments})
        return message

    def _list_attachments(self, message_id: str) -> tuple[EmailAttachmentMetadata, ...]:
        data = self.http_client.get_json(
            f"{GRAPH_API_BASE_URL}/me/messages/{quote(message_id)}/attachments?{urlencode({'$select': 'id,name,contentType,size'})}",
            headers=self._headers(),
        )
        return tuple(
            EmailAttachmentMetadata(
                id=_optional_str(item.get("id")),
                filename=str(item.get("name") or ""),
                mime_type=_optional_str(item.get("contentType")),
                size=_optional_int(item.get("size")),
            )
            for item in data.get("value", [])
            if isinstance(item, Mapping) and item.get("name")
        )

    def _headers(self, search: bool = False) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Prefer": 'outlook.body-content-type="text"',
        }
        if search:
            headers["ConsistencyLevel"] = "eventual"
        return headers


def _normalize_outlook_message(data: Mapping[str, Any]) -> EmailMessage:
    body = data.get("body") if isinstance(data.get("body"), Mapping) else {}
    body_content = _optional_str(body.get("content"))
    content_type = str(body.get("contentType", "")).lower()

    return EmailMessage(
        provider=EmailProvider.OUTLOOK,
        provider_message_id=str(data.get("id", "")),
        thread_id=_optional_str(data.get("conversationId")),
        subject=str(data.get("subject") or "(no subject)"),
        sender=_parse_graph_recipient(data.get("from")),
        recipients=tuple(
            address
            for recipient in data.get("toRecipients", [])
            if (address := _parse_graph_recipient(recipient)) is not None
        ),
        cc=tuple(
            address
            for recipient in data.get("ccRecipients", [])
            if (address := _parse_graph_recipient(recipient)) is not None
        ),
        received_at=parse_iso_datetime(_optional_str(data.get("receivedDateTime"))),
        snippet=_optional_str(data.get("bodyPreview")),
        plain_text=body_content if content_type == "text" else None,
        html=body_content if content_type == "html" else None,
        raw=data,
    )


def _parse_graph_recipient(value: Any) -> EmailAddress | None:
    if not isinstance(value, Mapping):
        return None
    email_address = value.get("emailAddress")
    if not isinstance(email_address, Mapping) or not email_address.get("address"):
        return None
    return EmailAddress(name=_optional_str(email_address.get("name")), email=str(email_address["address"]))


def _optional_str(value: Any) -> str | None:
    return str(value) if value is not None else None


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_access_token(value: str) -> str:
    token = value.strip()
    if token.lower().startswith("bearer "):
        return token[7:].strip()
    return token
