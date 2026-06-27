from __future__ import annotations

import unittest

from life_admin.scanner.email_agent_runner import (
    agent_result_diagnostics,
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


class DuplicateTaskAgent:
    def process_source_item(self, source_item):
        return {
            "status": "completed",
            "final_output": {
                "status": "saved",
                "items": [
                    {
                        "title": "Reply to Justin with final numbers",
                        "category": "reply_needed",
                        "summary": "Justin asked Tony to reply with the final numbers before the 3pm planning meeting.",
                        "recommended_next_action": "Confirm the final numbers and reply to Justin before the 3pm planning meeting.",
                        "due_date": "2026-06-27",
                        "priority": "high",
                        "confidence": 0.88,
                        "source_reasoning": "Direct reply request in the email.",
                        "needs_review": False,
                    },
                    {
                        "title": "Send project status update and final numbers",
                        "category": "task",
                        "summary": "Justin asked Tony to send the project status update by Friday and reply with the final numbers before the 3pm planning meeting.",
                        "recommended_next_action": "Reply to Justin with the final numbers before the 3pm planning meeting and prepare/send the project status update by Friday.",
                        "due_date": "2026-06-27",
                        "priority": "high",
                        "confidence": 0.94,
                        "source_reasoning": "The email contains two explicit asks.",
                        "needs_review": False,
                    },
                ]
            },
        }


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

    def test_process_email_source_items_merges_overlapping_task_like_outputs(self) -> None:
        results = process_email_source_items(
            DuplicateTaskAgent(),
            [
                {
                    "provider": "google",
                    "source_id": "gmail-3",
                    "content": "Justin asked Tony to send the project status update by Friday and reply with the final numbers before the 3pm planning meeting.",
                }
            ],
        )

        self.assertEqual(len(results), 1)
        items = results[0]["agent_result"]["final_output"]["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["category"], "task")
        self.assertIn("project status update", items[0]["summary"].lower())
        self.assertIn("final numbers", items[0]["recommended_next_action"].lower())
        self.assertIn("friday", items[0]["recommended_next_action"].lower())

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
                                    "due_date": "2026-06-30",
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
                                    "due_date": "",
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
        self.assertEqual(update["dashboard_items"][0]["dueAt"], "2026-06-30")
        self.assertEqual(len(update["dashboard_news"]), 1)
        self.assertEqual(update["dashboard_news"][0]["title"], "Grant digest")

    def test_dashboard_update_keeps_meetings_and_tasks_separate(self) -> None:
        update = dashboard_update_from_agent_results(
            [
                {
                    "source_key": "google:gmail-5",
                    "source_id": "gmail-5",
                    "agent_result": {
                        "final_output": {
                            "items": [
                                {
                                    "title": "Prepare planning deck",
                                    "category": "task",
                                    "summary": "Update the deck before the planning meeting.",
                                    "recommended_next_action": "Update and send the latest deck.",
                                    "due_date": "2026-06-29",
                                    "priority": "high",
                                    "confidence": 0.94,
                                    "source_reasoning": "Explicit request to update the deck.",
                                    "needs_review": False,
                                },
                                {
                                    "title": "Planning meeting prep",
                                    "category": "meeting",
                                    "summary": "Bring the updated deck to the planning meeting.",
                                    "recommended_next_action": "Review agenda and prepare talking points.",
                                    "due_date": "2026-06-30",
                                    "priority": "medium",
                                    "confidence": 0.91,
                                    "source_reasoning": "Meeting preparation is required.",
                                    "needs_review": False,
                                },
                            ]
                        }
                    },
                }
            ],
            created_at="2026-06-27",
        )

        self.assertEqual(len(update["dashboard_items"]), 2)
        item_types = [item["type"] for item in update["dashboard_items"]]
        self.assertIn("task", item_types)
        self.assertIn("meeting", item_types)
        due_dates = {item["title"]: item["dueAt"] for item in update["dashboard_items"]}
        self.assertEqual(due_dates["Prepare planning deck"], "2026-06-29")
        self.assertEqual(due_dates["Planning meeting prep"], "2026-06-30")

    def test_dashboard_update_from_agent_results_creates_fallback_review_item(self) -> None:
        update = dashboard_update_from_agent_results(
            [
                {
                    "source_key": "google:gmail-2",
                    "source_id": "gmail-2",
                    "agent_result": {
                        "status": "needs_review",
                        "final_output": {
                            "status": "needs_review",
                            "reason": "Classification was uncertain.",
                            "items": [],
                        },
                    },
                }
            ],
            created_at="2026-06-27",
        )

        self.assertEqual(len(update["dashboard_items"]), 1)
        self.assertEqual(update["dashboard_items"][0]["type"], "needs_review")
        self.assertIn("Classification was uncertain", update["dashboard_items"][0]["summary"])
        self.assertEqual(update["dashboard_items"][0]["dueAt"], "2026-06-27")

    def test_agent_result_diagnostics_counts_empty_and_needs_review_results(self) -> None:
        diagnostics = agent_result_diagnostics(
            [
                {
                    "source_id": "gmail-1",
                    "agent_result": {
                        "status": "completed",
                        "final_output": {"status": "saved", "items": []},
                    },
                },
                {
                    "source_id": "gmail-2",
                    "agent_result": {
                        "status": "needs_review",
                        "final_output": {
                            "status": "needs_review",
                            "reason": "Classification was uncertain.",
                            "items": [],
                        },
                    },
                },
                {
                    "source_id": "gmail-3",
                    "agent_result": {
                        "status": "completed",
                        "final_output": {
                            "status": "noise",
                            "reason": "Newsletter footer only.",
                            "items": [],
                        },
                    },
                },
            ]
        )

        self.assertEqual(diagnostics["empty_result_count"], 3)
        self.assertEqual(diagnostics["needs_review_count"], 1)
        self.assertEqual(diagnostics["noise_count"], 1)
        self.assertEqual(len(diagnostics["diagnostics"]), 3)
        self.assertEqual(diagnostics["diagnostics"][1]["status"], "needs_review")

    def test_process_email_source_items_keeps_distinct_partial_overlap_tasks(self) -> None:
        class PartialOverlapAgent:
            def process_source_item(self, source_item):
                return {
                    "status": "completed",
                    "final_output": {
                        "status": "saved",
                        "items": [
                            {
                                "title": "Reply to Justin with final numbers",
                                "category": "reply_needed",
                                "summary": "Justin asked Tony to reply with the final numbers before the 3pm planning meeting.",
                                "recommended_next_action": "Confirm the final numbers and reply to Justin before the 3pm planning meeting.",
                                "due_date": "2026-06-27",
                                "priority": "high",
                                "confidence": 0.88,
                                "source_reasoning": "Direct reply request in the email.",
                                "needs_review": False,
                            },
                            {
                                "title": "Send project status update",
                                "category": "task",
                                "summary": "Justin asked Tony to send the project status update by Friday.",
                                "recommended_next_action": "Prepare and send the project status update by Friday.",
                                "due_date": "2026-06-28",
                                "priority": "high",
                                "confidence": 0.94,
                                "source_reasoning": "Separate explicit request in the email.",
                                "needs_review": False,
                            },
                        ]
                    },
                }

        results = process_email_source_items(
            PartialOverlapAgent(),
            [
                {
                    "provider": "google",
                    "source_id": "gmail-4",
                    "content": "Justin asked Tony to send the project status update by Friday and reply with the final numbers before the 3pm planning meeting.",
                }
            ],
        )

        self.assertEqual(len(results), 1)
        items = results[0]["agent_result"]["final_output"]["items"]
        self.assertEqual(len(items), 2)

    def test_dashboard_update_falls_back_to_created_date_when_due_date_missing(self) -> None:
        update = dashboard_update_from_agent_results(
            [
                {
                    "source_key": "google:gmail-6",
                    "source_id": "gmail-6",
                    "agent_result": {
                        "final_output": {
                            "items": [
                                {
                                    "title": "Check with finance",
                                    "category": "task",
                                    "summary": "A follow-up is needed.",
                                    "recommended_next_action": "Check with finance.",
                                    "due_date": "",
                                    "priority": "medium",
                                    "confidence": 0.9,
                                    "source_reasoning": "No explicit date was given.",
                                    "needs_review": False,
                                }
                            ]
                        }
                    },
                }
            ],
            created_at="2026-06-27",
        )

        self.assertEqual(update["dashboard_items"][0]["dueAt"], "2026-06-27")


if __name__ == "__main__":
    unittest.main()
