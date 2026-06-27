from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, MutableSet

from agent import Agent
from schemas import SourceItem


def email_source_key(source_item: dict[str, Any]) -> str:
    provider = str(source_item.get("provider") or "email").strip() or "email"
    source_id = str(source_item.get("source_id") or "").strip()
    if source_id:
        return f"{provider}:{source_id}"
    return f"{provider}:{hash(str(source_item.get('content', '')))}"


def source_item_from_email_dict(source_item: dict[str, Any]) -> SourceItem:
    metadata = source_item.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    enriched_metadata = {
        **metadata,
        "provider": source_item.get("provider"),
        "thread_id": source_item.get("thread_id"),
        "title": source_item.get("title"),
        "received_at": source_item.get("received_at"),
    }

    return SourceItem(
        content=str(source_item.get("content") or ""),
        source_type=str(source_item.get("source_type") or "email"),
        source_id=str(source_item.get("source_id") or "") or None,
        metadata=enriched_metadata,
    )


def process_email_source_items(
    agent: Agent,
    source_items: Iterable[dict[str, Any]],
    *,
    seen_keys: MutableSet[str] | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    for raw_source_item in source_items:
        source_key = email_source_key(raw_source_item)
        if seen_keys is not None and source_key in seen_keys:
            continue

        source_item = source_item_from_email_dict(raw_source_item)
        if not source_item.content.strip():
            if seen_keys is not None:
                seen_keys.add(source_key)
            continue

        agent_result = agent.process_source_item(source_item)
        results.append(
            {
                "source_key": source_key,
                "source_id": source_item.source_id,
                "source_type": source_item.source_type,
                "agent_result": agent_result,
            }
        )

        if seen_keys is not None:
            seen_keys.add(source_key)

    return results


def dashboard_update_from_agent_results(
    agent_results: Iterable[dict[str, Any]],
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    created_date = created_at or datetime.now().date().isoformat()
    dashboard_items: list[dict[str, Any]] = []
    dashboard_news: list[dict[str, str]] = []

    for processed in agent_results:
        agent_result = processed.get("agent_result")
        if not isinstance(agent_result, dict):
            continue

        final_output = agent_result.get("final_output")
        if not isinstance(final_output, dict):
            continue

        source_id = str(processed.get("source_id") or processed.get("source_key") or "email")
        for index, item in enumerate(final_output.get("items", [])):
            if not isinstance(item, dict):
                continue

            if item.get("category") == "news" and not item.get("needs_review"):
                dashboard_news.append(
                    {
                        "title": str(item.get("title") or "Email update"),
                        "detail": str(item.get("summary") or item.get("recommended_next_action") or ""),
                    }
                )
                continue

            dashboard_items.append(
                {
                    "id": f"email-{source_id}-{index}",
                    "type": _dashboard_item_type(item),
                    "title": str(item.get("title") or "Email item"),
                    "owner": "Email",
                    "source": source_id,
                    "time": "From email",
                    "createdAt": created_date,
                    "dueAt": created_date,
                    "priority": _normalized_priority(item.get("priority")),
                    "confidence": _normalized_confidence(item.get("confidence")),
                    "summary": str(item.get("summary") or item.get("source_reasoning") or ""),
                    "next": str(item.get("recommended_next_action") or "Review the source email."),
                    "status": "open",
                }
            )

    return {
        "dashboard_items": dashboard_items,
        "dashboard_news": dashboard_news,
    }


def _dashboard_item_type(item: dict[str, Any]) -> str:
    if item.get("needs_review"):
        return "needs_review"
    category = str(item.get("category") or "").strip()
    if category == "meeting":
        return "meeting"
    return "task"


def _normalized_priority(value: Any) -> str:
    priority = str(value or "medium").lower()
    return priority if priority in {"low", "medium", "high"} else "medium"


def _normalized_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, confidence))
