from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, Iterable, MutableSet

from schemas import SourceItem

if TYPE_CHECKING:
    from agent import Agent

_TASK_LIKE_CATEGORIES = {"task", "deadline", "reply_needed", "follow_up"}
_STOPWORDS = {
    "a",
    "an",
    "and",
    "before",
    "by",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "please",
    "the",
    "to",
    "with",
}


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

        agent_result = _deduplicate_agent_result(agent.process_source_item(source_item))
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
        raw_items = final_output.get("items", [])
        if isinstance(raw_items, list) and raw_items:
            iterable_items = raw_items
        elif str(final_output.get("status") or agent_result.get("status") or "") == "needs_review":
            iterable_items = [
                {
                    "title": f"Review email {source_id}",
                    "category": "needs_review",
                    "summary": str(final_output.get("reason") or "The email needs review before it can be turned into a structured item."),
                    "recommended_next_action": "Inspect the source email and confirm the correct task, reply, or meeting follow-up.",
                    "due_date": created_date,
                    "priority": "medium",
                    "confidence": 0.0,
                    "source_reasoning": str(final_output.get("reason") or ""),
                    "needs_review": True,
                }
            ]
        else:
            iterable_items = []

        for index, item in enumerate(iterable_items):
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
                    "dueAt": _dashboard_due_date(item.get("due_date"), created_date),
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


def agent_result_diagnostics(agent_results: Iterable[dict[str, Any]]) -> dict[str, Any]:
    diagnostics: list[dict[str, Any]] = []
    empty_result_count = 0
    noise_count = 0
    needs_review_count = 0

    for processed in agent_results:
        source_id = str(processed.get("source_id") or processed.get("source_key") or "email")
        agent_result = processed.get("agent_result")
        if not isinstance(agent_result, dict):
            diagnostics.append(
                {
                    "source_id": source_id,
                    "status": "unknown",
                    "item_count": 0,
                    "reason": "Agent did not return a structured result.",
                }
            )
            empty_result_count += 1
            continue

        final_output = agent_result.get("final_output")
        if not isinstance(final_output, dict):
            diagnostics.append(
                {
                    "source_id": source_id,
                    "status": "unknown",
                    "item_count": 0,
                    "reason": "Agent result did not include a final output.",
                }
            )
            empty_result_count += 1
            continue

        status = str(final_output.get("status") or agent_result.get("status") or "unknown")
        items = final_output.get("items")
        item_count = len(items) if isinstance(items, list) else 0
        reason = str(final_output.get("reason") or "")

        if status == "noise":
            noise_count += 1
        if status == "needs_review" or any(
            isinstance(item, dict) and item.get("needs_review") for item in (items or []) if isinstance(items, list)
        ):
            needs_review_count += 1
        if item_count == 0:
            empty_result_count += 1

        diagnostics.append(
            {
                "source_id": source_id,
                "status": status,
                "item_count": item_count,
                "reason": reason,
            }
        )

    return {
        "diagnostics": diagnostics,
        "empty_result_count": empty_result_count,
        "noise_count": noise_count,
        "needs_review_count": needs_review_count,
    }


def _deduplicate_agent_result(agent_result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(agent_result, dict):
        return agent_result

    final_output = agent_result.get("final_output")
    if not isinstance(final_output, dict):
        return agent_result

    items = final_output.get("items")
    if not isinstance(items, list):
        return agent_result

    merged_items: list[dict[str, Any]] = []
    for raw_item in items:
        if not isinstance(raw_item, dict):
            continue

        item = dict(raw_item)
        match_index = next(
            (index for index, existing in enumerate(merged_items) if _items_should_merge(existing, item)),
            None,
        )
        if match_index is None:
            merged_items.append(item)
            continue

        merged_items[match_index] = _merge_items(merged_items[match_index], item)

    return {
        **agent_result,
        "final_output": {
            **final_output,
            "items": merged_items,
        },
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


def _items_should_merge(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left.get("needs_review") or right.get("needs_review"):
        return False

    left_category = str(left.get("category") or "").strip().lower()
    right_category = str(right.get("category") or "").strip().lower()
    if "news" in {left_category, right_category} or "meeting" in {left_category, right_category}:
        return False
    if left_category not in _TASK_LIKE_CATEGORIES or right_category not in _TASK_LIKE_CATEGORIES:
        return False

    left_tokens = _informative_tokens(_item_text(left))
    right_tokens = _informative_tokens(_item_text(right))
    if not left_tokens or not right_tokens:
        return False

    shared = left_tokens & right_tokens
    smaller_size = min(len(left_tokens), len(right_tokens))
    coverage = len(shared) / smaller_size if smaller_size else 0.0

    return len(shared) >= 4 and coverage >= 0.8


def _merge_items(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    return {
        **left,
        "title": _prefer_richer_text(left.get("title"), right.get("title")),
        "category": _merged_category(left.get("category"), right.get("category")),
        "summary": _prefer_richer_text(left.get("summary"), right.get("summary")),
        "recommended_next_action": _combine_text(
            left.get("recommended_next_action"),
            right.get("recommended_next_action"),
        ),
        "due_date": _merged_due_date(left.get("due_date"), right.get("due_date")),
        "priority": _max_priority(left.get("priority"), right.get("priority")),
        "confidence": max(_normalized_confidence(left.get("confidence")), _normalized_confidence(right.get("confidence"))),
        "source_reasoning": _combine_text(left.get("source_reasoning"), right.get("source_reasoning")),
        "needs_review": bool(left.get("needs_review")) or bool(right.get("needs_review")),
    }


def _merged_category(left: Any, right: Any) -> str:
    categories = [str(value or "").strip().lower() for value in (left, right)]
    for preferred in ("deadline", "task", "reply_needed", "follow_up"):
        if preferred in categories:
            return preferred
    return categories[0] or "task"


def _max_priority(left: Any, right: Any) -> str:
    order = {"low": 0, "medium": 1, "high": 2}
    normalized = [str(left or "medium").lower(), str(right or "medium").lower()]
    return max(normalized, key=lambda value: order.get(value, 1))


def _combine_text(left: Any, right: Any) -> str:
    left_text = _clean_text(left)
    right_text = _clean_text(right)
    if not left_text:
        return right_text
    if not right_text:
        return left_text

    normalized_left = _normalized_text(left_text)
    normalized_right = _normalized_text(right_text)
    if normalized_left in normalized_right:
        return right_text
    if normalized_right in normalized_left:
        return left_text
    return f"{left_text} Also: {right_text}"


def _prefer_richer_text(left: Any, right: Any) -> str:
    left_text = _clean_text(left)
    right_text = _clean_text(right)
    if not left_text:
        return right_text
    if not right_text:
        return left_text

    normalized_left = _normalized_text(left_text)
    normalized_right = _normalized_text(right_text)
    if normalized_left in normalized_right:
        return right_text
    if normalized_right in normalized_left:
        return left_text
    return right_text if len(_informative_tokens(right_text)) >= len(_informative_tokens(left_text)) else left_text


def _item_text(item: dict[str, Any]) -> str:
    return " ".join(
        _clean_text(item.get(field))
        for field in ("title", "summary", "recommended_next_action")
        if _clean_text(item.get(field))
    )


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _normalized_text(value: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", _clean_text(value).lower())).strip()


def _informative_tokens(value: Any) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", _normalized_text(value))
        if len(token) >= 3 and token not in _STOPWORDS
    }


def _dashboard_due_date(value: Any, fallback: str) -> str:
    normalized = _normalized_iso_date(value)
    return normalized or fallback


def _merged_due_date(left: Any, right: Any) -> str:
    left_date = _normalized_iso_date(left)
    right_date = _normalized_iso_date(right)
    if left_date and right_date:
        return min(left_date, right_date)
    return left_date or right_date or ""


def _normalized_iso_date(value: Any) -> str:
    text = str(value or "").strip()
    return text if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) else ""
