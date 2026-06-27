from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from life_admin.agent.tools.email_crawl import crawl_email_messages
from life_admin.integrations.email.types import HttpClient


@dataclass(frozen=True)
class EmailScanRequest:
    provider: str
    access_token: str
    query: str | None = None
    max_results: int = 10
    page_token: str | None = None


def scan_email_messages(
    request: EmailScanRequest,
    *,
    http_client: HttpClient | None = None,
) -> dict[str, Any]:
    """Read provider email and return normalized source items.

    Credentials are intentionally consumed only at the scanner/integration
    boundary. The agent loop should receive the returned source items later,
    not the provider access token.
    """
    page = crawl_email_messages(
        provider=request.provider,
        access_token=request.access_token,
        query=request.query,
        max_results=request.max_results,
        page_token=request.page_token,
        http_client=http_client,
    )

    return {
        "provider": request.provider,
        "source_items": page["source_items"],
        "next_page_token": page["next_page_token"],
        "count": len(page["source_items"]),
    }
