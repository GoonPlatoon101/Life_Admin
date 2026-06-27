from __future__ import annotations

from typing import Any

from life_admin.integrations.email import EmailSearchQuery, build_email_crawler
from life_admin.integrations.email.types import HttpClient


def crawl_email_messages(
    *,
    provider: str,
    access_token: str,
    query: str | None = None,
    max_results: int = 25,
    page_token: str | None = None,
    http_client: HttpClient | None = None,
) -> dict[str, Any]:
    """Agent tool: crawl a read-only page of Google or Outlook email messages.

    Returns SourceItem-like dictionaries that the bounded agent loop can pass to
    filter/classification/extraction tools. This tool only reads provider data.
    """
    crawler = build_email_crawler(provider=provider, access_token=access_token, http_client=http_client)
    page = crawler.list_messages(
        EmailSearchQuery(
            query=query,
            max_results=max_results,
            page_token=page_token,
        )
    )
    return {
        "source_items": [message.to_source_item() for message in page.messages],
        "next_page_token": page.next_page_token,
    }


def get_email_message(
    *,
    provider: str,
    access_token: str,
    message_id: str,
    http_client: HttpClient | None = None,
) -> dict[str, Any]:
    """Agent tool: fetch one read-only email message as a normalized source item."""
    crawler = build_email_crawler(provider=provider, access_token=access_token, http_client=http_client)
    return {"source_item": crawler.get_message(message_id).to_source_item()}

