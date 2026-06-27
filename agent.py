import json
from typing import Any

from openai import OpenAI

from config import Config
from llm_service import complete_with_retry
from schemas import AgentLoopLimits, AgentRunState, SourceItem
from tools import (
    classify_content,
    extract_email_actions,
    extract_meeting_context,
    extract_news_items,
    extract_tasks,
    filter_content,
    mark_needs_review,
    save_structured_output,
    validate_output,
)


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
        self.limits = AgentLoopLimits()

    def run(self) -> str | None:
        try:
            user_prompt = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting")
            return None

        if not user_prompt:
            return None

        result = self.process_source_item(SourceItem(content=user_prompt))
        return json.dumps(result["final_output"], indent=2)

    def process_source_item(self, source_item: SourceItem) -> dict[str, Any]:
        state = AgentRunState(source_item=source_item, limits=self.limits)

        filtered = self._call_tool(state, "filter_content", filter_content, source_item)
        if not filtered.get("is_relevant", False):
            return self._finish(
                state,
                "completed",
                {
                    "status": "noise",
                    "reason": filtered.get("reason", "Content was not relevant."),
                    "items": [],
                },
            )

        classification = self._call_tool(state, "classify_content", classify_content, source_item)
        categories = self._extract_categories(classification)
        if not categories or "noise" in categories or "uncertain" in categories:
            output = mark_needs_review(
                classification.get("reason", "Classification was uncertain."),
            )
            state.add_tool_call("mark_needs_review", output)
            return self._finish(state, "needs_review", output)

        extracted_items: list[dict[str, Any]] = []
        extraction_tools = self._select_extraction_tools(categories)
        if not extraction_tools:
            output = mark_needs_review(f"No extraction tool available for categories: {categories}")
            state.add_tool_call("mark_needs_review", output)
            return self._finish(state, "needs_review", output)

        for tool_name, tool_func in extraction_tools:
            extracted = self._call_tool(state, tool_name, tool_func, source_item)
            extracted_items.extend(extracted.get("items", []))

        validation = self._call_tool(
            state,
            "validate_output",
            lambda _client, _config, _source_item: validate_output(
                {"items": extracted_items},
                self.limits,
            ),
            source_item,
        )

        if validation.get("needs_review", True):
            output = mark_needs_review(
                validation.get("reason", "Validation requires review."),
                validation.get("items", extracted_items),
            )
            state.add_tool_call("mark_needs_review", output)
            return self._finish(state, "needs_review", output)

        output = save_structured_output(validation.get("items", extracted_items))
        state.add_tool_call("save_structured_output", output)
        return self._finish(state, "completed", output)

    def _call_tool(self, state, name, tool_func, source_item):
        if state.tool_call_count >= self.limits.max_tool_calls_per_item:
            raise RuntimeError("Agent loop exceeded max_tool_calls_per_item.")

        result = tool_func(self.client, self.config, source_item)
        state.add_tool_call(name, result)
        return result

    def _finish(
        self,
        state: AgentRunState,
        status: str,
        final_output: dict[str, Any],
    ) -> dict[str, Any]:
        state.status = status
        state.final_output = final_output
        return {
            "status": state.status,
            "final_output": state.final_output,
            "tool_calls": state.tool_calls,
        }

    def _extract_categories(self, classification: dict[str, Any]) -> list[str]:
        categories = classification.get("categories")
        if isinstance(categories, list):
            return [str(category) for category in categories]

        primary_category = classification.get("primary_category")
        if isinstance(primary_category, str):
            return [primary_category]

        category = classification.get("category")
        if isinstance(category, str):
            return [category]

        return []

    def _select_extraction_tools(self, categories: list[str]):
        selected = []
        if "task" in categories or "deadline" in categories or "follow_up" in categories:
            selected.append(("extract_tasks", extract_tasks))
        if "reply_needed" in categories:
            selected.append(("extract_email_actions", extract_email_actions))
        if "meeting" in categories:
            selected.append(("extract_meeting_context", extract_meeting_context))
        if "news" in categories:
            selected.append(("extract_news_items", extract_news_items))
        return selected
