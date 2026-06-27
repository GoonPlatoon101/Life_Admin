from __future__ import annotations

import json
from typing import Any, Mapping
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class EmailProviderError(RuntimeError):
    """Raised when an email provider returns an unusable response."""


class UrlLibHttpClient:
    def get_json(self, url: str, headers: Mapping[str, str] | None = None) -> Mapping[str, Any]:
        request = Request(url, headers=dict(headers or {}), method="GET")
        try:
            with urlopen(request, timeout=30) as response:
                payload = response.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise EmailProviderError(f"Email provider request failed: {exc.code} {body}") from exc

        data = json.loads(payload)
        if not isinstance(data, Mapping):
            raise EmailProviderError("Email provider returned non-object JSON.")
        return data

