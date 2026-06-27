import os
import unittest
from copy import deepcopy
from json import dumps
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent import Agent
from config import Config, load_config
from schemas import SourceItem


class FakeCompletions:
    def __init__(self, responses: list[dict] | None = None) -> None:
        self.kwargs = None
        self.calls = []
        self.responses = responses or [{"message": "Test response"}]

    def create(self, **kwargs):
        self.kwargs = deepcopy(kwargs)
        self.calls.append(deepcopy(kwargs))
        response = self.responses.pop(0)
        message = SimpleNamespace(content=dumps(response))
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


class FakeClient:
    def __init__(self, responses: list[dict] | None = None) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions(responses))


class AgentTests(unittest.TestCase):
    def _config(self):
        return Config(
            llm_api_key="test-key",
            llm_base_url="http://localhost:11434/v1",
            llm_model="qwen3",
            working_dir=Path.cwd(),
        )

    def test_agent_processes_source_item_through_loop(self):
        config = Config(
            llm_api_key="test-key",
            llm_base_url="http://localhost:11434/v1",
            llm_model="qwen3",
            working_dir=Path.cwd(),
        )
        client = FakeClient(
            [
                {"is_relevant": True, "reason": "Contains an action item.", "confidence": 0.95},
                {
                    "categories": ["task"],
                    "primary_category": "task",
                    "reason": "The user needs to do something.",
                    "confidence": 0.92,
                },
                {
                    "items": [
                        {
                            "title": "Send project update",
                            "category": "task",
                            "summary": "Send an update to Alex by Friday.",
                            "recommended_next_action": "Draft and send the update.",
                            "due_date": "2026-06-27",
                            "priority": "medium",
                            "confidence": 0.91,
                            "source_reasoning": "The source explicitly asks for an update.",
                            "needs_review": False,
                        }
                    ]
                },
            ]
        )
        agent = Agent(config=config, client=client, system_prompt="System prompt")

        with patch("builtins.input", return_value="What needs attention today?"):
            response = agent.run()

        self.assertIn('"status": "saved"', response)
        self.assertEqual(len(client.chat.completions.calls), 3)
        self.assertEqual(client.chat.completions.calls[0]["model"], "qwen3")
        self.assertEqual(client.chat.completions.calls[0]["temperature"], 0.0)

    def test_agent_marks_low_confidence_items_for_review(self):
        client = FakeClient(
            [
                {"is_relevant": True, "reason": "Contains an action item.", "confidence": 0.8},
                {
                    "categories": ["task"],
                    "primary_category": "task",
                    "reason": "Possible task.",
                    "confidence": 0.76,
                },
                {
                    "items": [
                        {
                            "title": "Check possible deadline",
                            "category": "task",
                            "summary": "There may be a deadline.",
                            "recommended_next_action": "Verify the deadline.",
                            "due_date": "",
                            "priority": "medium",
                            "confidence": 0.7,
                            "source_reasoning": "The source is ambiguous.",
                            "needs_review": False,
                        }
                    ]
                },
            ]
        )
        agent = Agent(config=self._config(), client=client, system_prompt="System prompt")

        with patch("builtins.input", return_value="Maybe I owe Sam the report soon"):
            response = agent.run()

        self.assertIn('"status": "needs_review"', response)
        self.assertIn('"needs_review": true', response)

    def test_agent_keeps_work_coordination_email_when_filter_marks_it_irrelevant(self):
        client = FakeClient(
            [
                {"is_relevant": False, "reason": "This is a work coordination message about a presentation deck.", "confidence": 0.91},
                {
                    "categories": ["task", "meeting"],
                    "primary_category": "task",
                    "reason": "It includes a work task tied to a meeting.",
                    "confidence": 0.92,
                },
                {
                    "items": [
                        {
                            "title": "Update the presentation deck",
                            "category": "task",
                            "summary": "Prepare the presentation deck before the planning meeting.",
                            "recommended_next_action": "Update the deck and send the latest version before the planning meeting.",
                            "due_date": "2026-06-27",
                            "priority": "high",
                            "confidence": 0.93,
                            "source_reasoning": "The email asks for deck updates before a meeting.",
                            "needs_review": False,
                        }
                    ]
                },
                {
                    "items": [
                        {
                            "title": "Prepare for the planning meeting",
                            "category": "meeting",
                            "summary": "The presentation deck needs to be ready for the planning meeting.",
                            "recommended_next_action": "Bring the updated deck to the planning meeting.",
                            "due_date": "2026-06-27",
                            "priority": "medium",
                            "confidence": 0.9,
                            "source_reasoning": "Meeting preparation is explicitly implied.",
                            "needs_review": False,
                        }
                    ]
                },
            ]
        )
        agent = Agent(config=self._config(), client=client, system_prompt="System prompt")

        result = agent.process_source_item(
            SourceItem(content="Please update the presentation deck and have it ready before the planning meeting.")
        )

        self.assertEqual(result["final_output"]["status"], "saved")
        self.assertEqual(len(result["final_output"]["items"]), 2)
        self.assertEqual(len(client.chat.completions.calls), 4)

    def test_agent_uses_fallback_categories_when_classification_returns_noise(self):
        client = FakeClient(
            [
                {"is_relevant": True, "reason": "Contains project coordination.", "confidence": 0.86},
                {
                    "categories": ["noise"],
                    "primary_category": "noise",
                    "reason": "Work coordination message.",
                    "confidence": 0.78,
                },
                {
                    "items": [
                        {
                            "title": "Send project status update",
                            "category": "task",
                            "summary": "Send the project status update by Friday.",
                            "recommended_next_action": "Prepare and send the project status update by Friday.",
                            "due_date": "2026-06-27",
                            "priority": "high",
                            "confidence": 0.9,
                            "source_reasoning": "The request is explicit in the email.",
                            "needs_review": False,
                        }
                    ]
                },
            ]
        )
        agent = Agent(config=self._config(), client=client, system_prompt="System prompt")

        result = agent.process_source_item(
            SourceItem(content="Please send the project status update by Friday.")
        )

        self.assertEqual(result["final_output"]["status"], "saved")
        self.assertEqual(result["final_output"]["items"][0]["title"], "Send project status update")
        self.assertEqual(len(client.chat.completions.calls), 3)

    def test_load_config_reads_env_file(self):
        old_values = {
            "LLM_API_KEY": os.environ.pop("LLM_API_KEY", None),
            "LLM_BASE_URL": os.environ.pop("LLM_BASE_URL", None),
            "LLM_MODEL": os.environ.pop("LLM_MODEL", None),
        }
        try:
            test_dir = Path("tests") / "tmp_config"
            test_dir.mkdir(exist_ok=True)
            (test_dir / ".env").write_text(
                "\n".join(
                    [
                        "LLM_API_KEY=ollama",
                        "LLM_BASE_URL=http://localhost:11434/v1",
                        "LLM_MODEL=qwen3",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_config(test_dir)

            self.assertEqual(config.llm_api_key, "ollama")
            self.assertEqual(config.llm_base_url, "http://localhost:11434/v1")
            self.assertEqual(config.llm_model, "qwen3")
            self.assertEqual(config.working_dir, test_dir)
        finally:
            for key, value in old_values.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            env_file = Path("tests") / "tmp_config" / ".env"
            if env_file.exists():
                env_file.unlink()
            tmp_dir = Path("tests") / "tmp_config"
            if tmp_dir.exists():
                tmp_dir.rmdir()


if __name__ == "__main__":
    unittest.main()
