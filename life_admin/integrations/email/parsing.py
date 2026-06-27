from __future__ import annotations

from datetime import datetime, timezone
from email.utils import getaddresses, parsedate_to_datetime

from life_admin.integrations.email.types import EmailAddress


def parse_addresses(value: str | None) -> tuple[EmailAddress, ...]:
    if not value:
        return ()
    parsed = []
    for name, address in getaddresses([value]):
        if address:
            parsed.append(EmailAddress(name=name or None, email=address))
    return tuple(parsed)


def parse_first_address(value: str | None) -> EmailAddress | None:
    addresses = parse_addresses(value)
    return addresses[0] if addresses else None


def parse_email_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None

