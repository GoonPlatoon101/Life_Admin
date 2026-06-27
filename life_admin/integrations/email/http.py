from __future__ import annotations

import json
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
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
            raise EmailProviderError(_provider_error_message(exc.code, body)) from exc
        except URLError as exc:
            reason = getattr(exc, "reason", exc)
            raise EmailProviderError(f"Email provider request failed: {reason}") from exc
        except TimeoutError as exc:
            raise EmailProviderError("Email provider request timed out.") from exc

        data = json.loads(payload)
        if not isinstance(data, Mapping):
            raise EmailProviderError("Email provider returned non-object JSON.")
        return data


def _provider_error_message(status_code: int, body: str) -> str:
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        data = None

    if isinstance(data, Mapping):
        error = data.get("error")
        if isinstance(error, Mapping):
            message = error.get("message") or error.get("error_description")
            status = error.get("status")
            if message:
                return f"Email provider request failed: {status_code} {status or ''} {message}".strip()
        if isinstance(error, str):
            description = data.get("error_description")
            return f"Email provider request failed: {status_code} {error} {description or ''}".strip()

    compact_body = body.strip().replace("\n", " ")
    return f"Email provider request failed: {status_code} {compact_body}".strip()

