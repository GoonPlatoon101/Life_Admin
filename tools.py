from typing import Any

from openai import OpenAI

from config import Config
from llm_service import complete_json_with_retry
from schemas import AgentLoopLimits, SourceItem


def _call_json_tool(
    client: OpenAI,
    config: Config,
    *,
    tool_name: str,
    instruction: str,
    content: str,
) -> dict[str, Any]:
    output_contract = (
        "Output contract: return exactly one top-level JSON object. "
        "Do not return a JSON array, string, number, boolean, null, markdown, or commentary. "
        "Use double quotes for all JSON keys and string values."
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You are a LifeAdmin extraction tool. Return only valid JSON. "
                f"{output_contract}"
            ),
        },
        {
            "role": "user",
            "content": (
                f"Tool: {tool_name}\n\n"
                f"{output_contract}\n\n"
                f"Instruction:\n{instruction}\n\n"
                f"Content:\n{content}"
            ),
        },
    ]
    return complete_json_with_retry(
        client,
        model=config.llm_model,
        messages=messages,
        temperature=0.0,
    )


def filter_content(client: OpenAI, config: Config, source_item: SourceItem) -> dict[str, Any]:
    return _call_json_tool(
        client,
        config,
        tool_name="filter_content",
        instruction=(
            "Decide whether this content is worth processing for life admin. "
            "Return a JSON object with exactly these keys: "
            '{"is_relevant": boolean, "reason": string, "confidence": number}. '
            "confidence must be between 0 and 1."
        ),
        content=source_item.content,
    )


def classify_content(client: OpenAI, config: Config, source_item: SourceItem) -> dict[str, Any]:
    return _call_json_tool(
        client,
        config,
        tool_name="classify_content",
        instruction=(
            "Classify the content into one or more categories from: task, deadline, "
            "meeting, reply_needed, follow_up, news, noise, uncertain. Return a JSON object "
            "with exactly these keys: "
            '{"categories": [string], "primary_category": string, "reason": string, '
            '"confidence": number}. confidence must be between 0 and 1.'
        ),
        content=source_item.content,
    )


def extract_tasks(client: OpenAI, config: Config, source_item: SourceItem) -> dict[str, Any]:
    return _call_json_tool(
        client,
        config,
        tool_name="extract_tasks",
        instruction=(
            "Extract actionable tasks and deadlines. Return a JSON object with exactly one "
            'top-level key: {"items": [item]}. Each item must be a JSON object with exactly '
            "these keys: title, category, summary, recommended_next_action, priority, "
            "confidence, source_reasoning, needs_review. confidence must be a number from "
            "0 to 1. needs_review must be a boolean. If there are no tasks, return "
            '{"items": []}.'
        ),
        content=source_item.content,
    )


def extract_email_actions(client: OpenAI, config: Config, source_item: SourceItem) -> dict[str, Any]:
    return _call_json_tool(
        client,
        config,
        tool_name="extract_email_actions",
        instruction=(
            "Detect whether a reply is needed and extract reply guidance. Return a JSON object "
            'with exactly one top-level key: {"items": [item]}. Each item must be a JSON '
            "object with exactly these keys: title, category, summary, "
            "recommended_next_action, priority, confidence, source_reasoning, needs_review. "
            "confidence must be a number from 0 to 1. needs_review must be a boolean. "
            'If no reply is needed, return {"items": []}.'
        ),
        content=source_item.content,
    )


def extract_meeting_context(client: OpenAI, config: Config, source_item: SourceItem) -> dict[str, Any]:
    return _call_json_tool(
        client,
        config,
        tool_name="extract_meeting_context",
        instruction=(
            "Extract meeting prep notes, agenda hints, and follow-up tasks. Return a JSON object "
            'with exactly one top-level key: {"items": [item]}. Each item must be a JSON '
            "object with exactly these keys: title, category, summary, "
            "recommended_next_action, priority, confidence, source_reasoning, needs_review. "
            "confidence must be a number from 0 to 1. needs_review must be a boolean. "
            'If there is no meeting context, return {"items": []}.'
        ),
        content=source_item.content,
    )


def extract_news_items(client: OpenAI, config: Config, source_item: SourceItem) -> dict[str, Any]:
    return _call_json_tool(
        client,
        config,
        tool_name="extract_news_items",
        instruction=(
            "Summarize informative updates or newsletters. Return a JSON object with exactly "
            'one top-level key: {"items": [item]}. Each item must be a JSON object with '
            "exactly these keys: title, category, summary, recommended_next_action, priority, "
            "confidence, source_reasoning, needs_review. confidence must be a number from "
            "0 to 1. needs_review must be a boolean. If there are no informative updates, "
            'return {"items": []}.'
        ),
        content=source_item.content,
    )


def validate_output(
    extracted: dict[str, Any],
    limits: AgentLoopLimits,
) -> dict[str, Any]:
    required_fields = {
        "title",
        "category",
        "summary",
        "recommended_next_action",
        "priority",
        "confidence",
        "source_reasoning",
        "needs_review",
    }
    items = extracted.get("items")
    if not isinstance(items, list):
        return {
            "valid": False,
            "needs_review": True,
            "reason": "Extraction did not return an items array.",
        }

    problems: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            problems.append(f"Item {index} is not an object.")
            continue

        missing = sorted(required_fields - set(item))
        if missing:
            problems.append(f"Item {index} is missing fields: {', '.join(missing)}.")

        confidence = item.get("confidence")
        if not isinstance(confidence, int | float):
            problems.append(f"Item {index} has invalid confidence.")
            item["needs_review"] = True
        elif confidence < limits.min_confidence_to_avoid_needs_review:
            item["needs_review"] = True

    return {
        "valid": not problems,
        "needs_review": bool(problems)
        or any(item.get("needs_review") for item in items if isinstance(item, dict)),
        "reason": " ".join(problems) if problems else "Output passed validation.",
        "items": items,
    }


def save_structured_output(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"status": "saved", "items": items}


def mark_needs_review(reason: str, items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"status": "needs_review", "reason": reason, "items": items or []}
