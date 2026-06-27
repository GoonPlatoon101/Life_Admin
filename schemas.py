from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentLoopLimits:
    max_tool_calls_per_item: int = 6
    max_retries_per_item: int = 2
    min_confidence_to_auto_save: float = 0.75
    min_confidence_to_avoid_needs_review: float = 0.85


@dataclass(frozen=True)
class SourceItem:
    content: str
    source_type: str = "user_input"
    source_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentRunState:
    source_item: SourceItem
    limits: AgentLoopLimits
    status: str = "running"
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    final_output: dict[str, Any] | None = None

    def add_tool_call(self, name: str, result: dict[str, Any]) -> None:
        self.tool_calls.append({"tool_name": name, "result": result})

    @property
    def tool_call_count(self) -> int:
        return len(self.tool_calls)
