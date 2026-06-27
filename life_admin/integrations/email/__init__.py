"""Email provider crawlers."""

from life_admin.integrations.email.factory import build_email_crawler
from life_admin.integrations.email.types import EmailMessage, EmailPage, EmailProvider, EmailSearchQuery

__all__ = [
    "EmailMessage",
    "EmailPage",
    "EmailProvider",
    "EmailSearchQuery",
    "build_email_crawler",
]

