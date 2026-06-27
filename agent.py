from typing import Any

from openai import OpenAI

from config import Config
from llm_service import complete_with_retry


class Agent:
    def __init__(
        self,
        config: Config,
        client: OpenAI,
        system_prompt: str,
    ) -> None:
        self.config = config
        self.client = client
        self.messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]

    def run(self) -> str | None:
        try:
            user_prompt = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting")
            return None

        if not user_prompt:
            return None

        self.messages.append({"role": "user", "content": user_prompt})

        response = complete_with_retry(
            self.client,
            model=self.config.llm_model,
            messages=self.messages,
            temperature=0.2,
        )

        assistant_message = response.choices[0].message.content
        self.messages.append({"role": "assistant", "content": assistant_message})
        return assistant_message
