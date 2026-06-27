from __future__ import annotations

import unittest

from life_admin.scanner.email_agent_runner import (
    dashboard_update_from_agent_results,
    email_source_key,
    process_email_source_items,
    source_item_from_email_dict,
)


class FakeAgent:
    def __init__(self) -> None:
        self.source_items = []

    def process_source_item(self, source_item):
        self.source_items.append(source_item)
        return {"status": "completed", "final_output": {"status": "saved", "items": []}}


class EmailAgentRunnerTest(unittest.TestCase):
    def test_source_item_from_email_dict_preserves_content_and_metadata(self) -> None:
        source_item = source_item_from_email_dict(
            {
                "source_type": "email",
                "provider": "google",
                "source_id": "gmail-1",
                "thread_id": "thread-1",
                "title": "Budget request",
                "content": "Please send the budget by Friday.",
                "received_at": "2026-06-26T10:30:00+00:00",
                "metadata": {"from": {"email": "ava@example.com"}},
            }
        )

        self.assertEqual(source_item.source_type, "email")
        self.assertEqual(source_item.source_id, "gmail-1")
        self.assertIn("budget", source_item.content)
        self.assertEqual(source_item.metadata["provider"], "google")
        self.assertEqual(source_item.metadata["from"]["email"], "ava@example.com")

    def test_process_email_source_items_skips_seen_messages(self) -> None:
        agent = FakeAgent()
        seen_keys = {"google:gmail-1"}

        results = process_email_source_items(
            agent,
            [
                {"provider": "google", "source_id": "gmail-1", "content": "Old"},
                {"provider": "google", "source_id": "gmail-2", "content": "New task"},
            ],
            seen_keys=seen_keys,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source_key"], "google:gmail-2")
        self.assertEqual(len(agent.source_items), 1)
        self.assertIn("google:gmail-2", seen_keys)

    def test_email_source_key_uses_provider_and_source_id(self) -> None:
        self.assertEqual(
            email_source_key({"provider": "outlook", "source_id": "message-1"}),
            "outlook:message-1",
        )

    def test_dashboard_update_from_agent_results_maps_items_for_queue(self) -> None:
        update = dashboard_update_from_agent_results(
            [
                {
                    "source_key": "google:gmail-1",
                    "source_id": "gmail-1",
                    "agent_result": {
                        "final_output": {
                            "items": [
                                {
                                    "title": "Send budget",
                                    "category": "task",
                                    "summary": "Ava asked for the budget by Friday.",
                                    "recommended_next_action": "Reply with the budget.",
                                    "priority": "high",
                                    "confidence": 0.92,
                                    "source_reasoning": "Explicit request in email.",
                                    "needs_review": False,
                                },
                                {
                                    "title": "Grant digest",
                                    "category": "news",
                                    "summary": "New grant applications opened.",
                                    "recommended_next_action": "Read later.",
                                    "priority": "low",
                                    "confidence": 0.9,
                                    "source_reasoning": "Newsletter content.",
                                    "needs_review": False,
                                },
                            ]
                        }
                    },
                }
            ],
            created_at="2026-06-27",
        )

        self.assertEqual(len(update["dashboard_items"]), 1)
        self.assertEqual(update["dashboard_items"][0]["type"], "task")
        self.assertEqual(update["dashboard_items"][0]["title"], "Send budget")
        self.assertEqual(update["dashboard_items"][0]["createdAt"], "2026-06-27")
        self.assertEqual(len(update["dashboard_news"]), 1)
        self.assertEqual(update["dashboard_news"][0]["title"], "Grant digest")


if __name__ == "__main__":
    unittest.main()
