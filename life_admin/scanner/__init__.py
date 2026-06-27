"""Scanner entry points for read-only external data ingestion."""

from life_admin.scanner.email_scanner import EmailScanRequest, scan_email_messages

__all__ = ["EmailScanRequest", "scan_email_messages"]
