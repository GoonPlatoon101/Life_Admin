from __future__ import annotations

from life_admin.integrations.email.google import GoogleEmailCrawler
from life_admin.integrations.email.outlook import OutlookEmailCrawler
from life_admin.integrations.email.types import EmailCrawler, EmailProvider, HttpClient


def build_email_crawler(
    provider: EmailProvider | str,
    access_token: str,
    http_client: HttpClient | None = None,
) -> EmailCrawler:
    normalized_provider = EmailProvider(provider)
    if normalized_provider is EmailProvider.GOOGLE:
        return GoogleEmailCrawler(access_token=access_token, http_client=http_client)
    if normalized_provider is EmailProvider.OUTLOOK:
        return OutlookEmailCrawler(access_token=access_token, http_client=http_client)
    raise ValueError(f"Unsupported email provider: {provider}")

