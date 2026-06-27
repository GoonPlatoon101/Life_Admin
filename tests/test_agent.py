import os
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent import Agent
from config import Config, load_config


class FakeCompletions:
    def __init__(self) -> None:
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = deepcopy(kwargs)
        message = SimpleNamespace(content="Test response")
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


class FakeClient:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions())


class AgentTests(unittest.TestCase):
    def test_agent_sends_user_prompt_and_stores_response(self):
        config = Config(
            llm_api_key="test-key",
            llm_base_url="http://localhost:11434/v1",
            llm_model="qwen3",
            working_dir=Path.cwd(),
        )
        client = FakeClient()
        agent = Agent(config=config, client=client, system_prompt="System prompt")

        with patch("builtins.input", return_value="What needs attention today?"):
            response = agent.run()

        self.assertEqual(response, "Test response")
        self.assertEqual(client.chat.completions.kwargs["model"], "qwen3")
        self.assertEqual(client.chat.completions.kwargs["temperature"], 0.2)
        self.assertEqual(
            client.chat.completions.kwargs["messages"],
            [
                {"role": "system", "content": "System prompt"},
                {"role": "user", "content": "What needs attention today?"},
            ],
        )
        self.assertEqual(agent.messages[-1], {"role": "assistant", "content": "Test response"})

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
