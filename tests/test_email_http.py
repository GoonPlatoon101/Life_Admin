from __future__ import annotations

import unittest

from life_admin.integrations.email.http import _provider_error_message


class EmailHttpTest(unittest.TestCase):
    def test_provider_error_message_extracts_google_error_message(self) -> None:
        message = _provider_error_message(
            401,
            '{"error": {"status": "UNAUTHENTICATED", "message": "Invalid Credentials"}}',
        )

        self.assertEqual(
            message,
            "Email provider request failed: 401 UNAUTHENTICATED Invalid Credentials",
        )


if __name__ == "__main__":
    unittest.main()
