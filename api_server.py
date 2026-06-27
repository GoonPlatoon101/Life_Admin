from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from life_admin.scanner import EmailScanRequest, scan_email_messages


HOST = "127.0.0.1"
PORT = 8000
ROOT = Path(__file__).resolve().parent


class LifeAdminHandler(BaseHTTPRequestHandler):
    server_version = "LifeAdminAPI/0.1"

    def do_GET(self) -> None:
        path = self._static_path()
        if path is None:
            self._send_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)
            return

        content_type, _ = mimetypes.guess_type(path.name)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(path.read_bytes())

    def do_POST(self) -> None:
        if self.path != "/api/email/scan":
            self._send_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)
            return

        try:
            payload = self._read_json()
            request = EmailScanRequest(
                provider=str(payload.get("provider", "")).strip(),
                access_token=str(payload.get("access_token", "")).strip(),
                query=_optional_str(payload.get("query")),
                max_results=_bounded_int(payload.get("max_results"), default=10, minimum=1, maximum=25),
                page_token=_optional_str(payload.get("page_token")),
            )
            _validate_scan_request(request)
            result = scan_email_messages(request)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        except Exception as exc:
            self._send_json(
                {"error": "Email scan failed.", "detail": str(exc)},
                status=HTTPStatus.BAD_GATEWAY,
            )
            return

        self._send_json(result)

    def log_message(self, format: str, *args: Any) -> None:
        if self.path == "/api/email/scan":
            print(f"{self.address_string()} - email scan request")
            return
        super().log_message(format, *args)

    def _static_path(self) -> Path | None:
        raw_path = self.path.split("?", 1)[0]
        relative = "index.html" if raw_path == "/" else unquote(raw_path).lstrip("/")
        path = (ROOT / relative).resolve()
        if not path.is_file() or ROOT not in path.parents and path != ROOT:
            return None
        return path

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            raise ValueError("Request body is required.")
        body = self.rfile.read(length).decode("utf-8")
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object.")
        return data

    def _send_json(self, payload: dict[str, Any], *, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def _validate_scan_request(request: EmailScanRequest) -> None:
    if request.provider not in {"google", "outlook"}:
        raise ValueError("provider must be either 'google' or 'outlook'.")
    if not request.access_token:
        raise ValueError("access_token is required.")


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), LifeAdminHandler)
    print(f"LifeAdmin running at http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
