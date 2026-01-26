"""
Analytics Instrumentation Service

Tracks agent invocations, tool success/failure rates, and system health metrics
to enable data-driven improvements and debugging.
"""

import time
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Any
from collections import defaultdict
from enum import Enum

from app.models.agent_protocols import ToolErrorCode


class MetricType(str, Enum):
    """Types of metrics tracked."""
    AGENT_INVOCATION = "agent_invocation"
    TOOL_SUCCESS = "tool_success"
    TOOL_FAILURE = "tool_failure"
    LOCATION_RESOLUTION = "location_resolution"
    USER_CLARIFICATION = "user_clarification"
    CROSS_CHAT_LEAKAGE = "cross_chat_leakage"  # Should be 0 after fix
    CONVERSATION_CREATED = "conversation_created"
    MESSAGE_SENT = "message_sent"


@dataclass
class MetricEvent:
    """A single metric event."""
    metric_type: MetricType
    timestamp: datetime
    user_id: str | None = None
    tenant_id: str | None = None
    conversation_id: str | None = None
    agent_name: str | None = None
    tool_name: str | None = None
    success: bool = True
    error_code: str | None = None
    duration_ms: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_type": self.metric_type.value,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "conversation_id": self.conversation_id,
            "agent_name": self.agent_name,
            "tool_name": self.tool_name,
            "success": self.success,
            "error_code": self.error_code,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }


class AnalyticsCollector:
    """
    In-memory analytics collector for tracking metrics.

    In production, this would write to a time-series database or analytics service.
    For now, it maintains rolling counters and recent events for debugging.
    """

    def __init__(self, max_events: int = 10000, retention_hours: int = 24):
        self.max_events = max_events
        self.retention_hours = retention_hours
        self.events: list[MetricEvent] = []

        # Rolling counters
        self.counters: dict[str, int] = defaultdict(int)
        self.error_counters: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        # Timing stats
        self.timing_sums: dict[str, int] = defaultdict(int)
        self.timing_counts: dict[str, int] = defaultdict(int)

    def record(self, event: MetricEvent) -> None:
        """Record a metric event."""
        # Add to events list
        self.events.append(event)

        # Trim if necessary
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]

        # Update counters
        key = f"{event.metric_type.value}"
        self.counters[key] += 1

        if event.tool_name:
            tool_key = f"{event.metric_type.value}:{event.tool_name}"
            self.counters[tool_key] += 1

            if not event.success and event.error_code:
                self.error_counters[event.tool_name][event.error_code] += 1

        # Update timing stats
        if event.duration_ms is not None:
            timing_key = event.tool_name or event.agent_name or event.metric_type.value
            self.timing_sums[timing_key] += event.duration_ms
            self.timing_counts[timing_key] += 1

    def record_agent_invocation(
        self,
        agent_name: str,
        user_id: str | None = None,
        conversation_id: str | None = None,
        success: bool = True,
        duration_ms: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record an agent invocation."""
        self.record(MetricEvent(
            metric_type=MetricType.AGENT_INVOCATION,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            conversation_id=conversation_id,
            agent_name=agent_name,
            success=success,
            duration_ms=duration_ms,
            metadata=metadata or {},
        ))

    def record_tool_result(
        self,
        tool_name: str,
        success: bool,
        user_id: str | None = None,
        conversation_id: str | None = None,
        error_code: ToolErrorCode | str | None = None,
        duration_ms: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a tool execution result."""
        error_str = error_code.value if isinstance(error_code, ToolErrorCode) else error_code
        self.record(MetricEvent(
            metric_type=MetricType.TOOL_SUCCESS if success else MetricType.TOOL_FAILURE,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            conversation_id=conversation_id,
            tool_name=tool_name,
            success=success,
            error_code=error_str,
            duration_ms=duration_ms,
            metadata=metadata or {},
        ))

    def record_location_resolution(
        self,
        location_input: str,
        success: bool,
        method: str | None = None,
        confidence: str | None = None,
        duration_ms: int | None = None,
        user_id: str | None = None,
        conversation_id: str | None = None,
    ) -> None:
        """Record a location resolution attempt."""
        self.record(MetricEvent(
            metric_type=MetricType.LOCATION_RESOLUTION,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            conversation_id=conversation_id,
            success=success,
            duration_ms=duration_ms,
            metadata={
                "location_input": location_input[:100],  # Truncate for privacy
                "method": method,
                "confidence": confidence,
            },
        ))

    def record_user_clarification(
        self,
        reason: str,
        user_id: str | None = None,
        conversation_id: str | None = None,
        agent_name: str | None = None,
    ) -> None:
        """Record when user clarification was required."""
        self.record(MetricEvent(
            metric_type=MetricType.USER_CLARIFICATION,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            conversation_id=conversation_id,
            agent_name=agent_name,
            metadata={"reason": reason},
        ))

    def record_cross_chat_leakage_detection(
        self,
        user_id: str,
        conversation_id: str,
        leaked_data_type: str,
        source_conversation_id: str | None = None,
    ) -> None:
        """
        Record a detected cross-chat leakage incident.
        This should become 0 after the fix is implemented.
        """
        self.record(MetricEvent(
            metric_type=MetricType.CROSS_CHAT_LEAKAGE,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            conversation_id=conversation_id,
            success=False,  # Leakage is a failure
            metadata={
                "leaked_data_type": leaked_data_type,
                "source_conversation_id": source_conversation_id,
            },
        ))

    def get_summary(self, hours: int = 24) -> dict[str, Any]:
        """Get a summary of metrics for the specified time period."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent_events = [e for e in self.events if e.timestamp > cutoff]

        # Count by type
        type_counts: dict[str, int] = defaultdict(int)
        for event in recent_events:
            type_counts[event.metric_type.value] += 1

        # Tool success/failure rates
        tool_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"success": 0, "failure": 0})
        for event in recent_events:
            if event.tool_name:
                if event.success:
                    tool_stats[event.tool_name]["success"] += 1
                else:
                    tool_stats[event.tool_name]["failure"] += 1

        # Calculate success rates
        tool_success_rates: dict[str, float] = {}
        for tool_name, stats in tool_stats.items():
            total = stats["success"] + stats["failure"]
            if total > 0:
                tool_success_rates[tool_name] = stats["success"] / total

        # Average timing
        avg_timing: dict[str, float] = {}
        for key in self.timing_counts:
            if self.timing_counts[key] > 0:
                avg_timing[key] = self.timing_sums[key] / self.timing_counts[key]

        return {
            "period_hours": hours,
            "total_events": len(recent_events),
            "counts_by_type": dict(type_counts),
            "tool_stats": dict(tool_stats),
            "tool_success_rates": tool_success_rates,
            "average_timing_ms": avg_timing,
            "top_errors": dict(self.error_counters),
            "cross_chat_leakage_count": type_counts.get(MetricType.CROSS_CHAT_LEAKAGE.value, 0),
            "user_clarification_count": type_counts.get(MetricType.USER_CLARIFICATION.value, 0),
        }

    def get_insights(self) -> dict[str, Any]:
        """
        Analyze metrics and generate insights/hypotheses.
        This is the "Insights Agent" capability.
        """
        summary = self.get_summary(hours=168)  # Last week

        insights = []
        hypotheses = []
        recommendations = []

        # Check tool failure rates
        for tool_name, rate in summary.get("tool_success_rates", {}).items():
            if rate < 0.9:  # Less than 90% success
                failure_rate = (1 - rate) * 100
                insights.append(f"{tool_name} has {failure_rate:.1f}% failure rate")

                # Check error distribution
                errors = summary.get("top_errors", {}).get(tool_name, {})
                if errors:
                    top_error = max(errors.items(), key=lambda x: x[1])
                    hypotheses.append(
                        f"Hypothesis: {tool_name} failures are primarily due to {top_error[0]} "
                        f"({top_error[1]} occurrences)"
                    )

        # Check location resolution
        location_events = [
            e for e in self.events
            if e.metric_type == MetricType.LOCATION_RESOLUTION
        ]
        if location_events:
            success_count = sum(1 for e in location_events if e.success)
            total = len(location_events)
            if total > 0:
                success_rate = success_count / total
                if success_rate < 0.95:
                    insights.append(
                        f"Location resolution success rate: {success_rate*100:.1f}%"
                    )
                    hypotheses.append(
                        "Hypothesis: Users are providing ambiguous location inputs "
                        "(city-only without ZIP) that require clarification"
                    )
                    recommendations.append(
                        "Experiment: Add autocomplete for location input with ZIP suggestions"
                    )

        # Check cross-chat leakage
        leakage_count = summary.get("cross_chat_leakage_count", 0)
        if leakage_count > 0:
            insights.append(f"CRITICAL: {leakage_count} cross-chat leakage events detected")
            hypotheses.append(
                "Hypothesis: User preferences or cached data is bleeding into new conversations"
            )
            recommendations.append(
                "Action: Audit conversation initialization for proper scope isolation"
            )
        else:
            insights.append("Cross-chat isolation is working correctly (0 leakage events)")

        # Check user clarification rate
        clarification_count = summary.get("user_clarification_count", 0)
        total_messages = summary.get("counts_by_type", {}).get(MetricType.MESSAGE_SENT.value, 0)
        if total_messages > 0:
            clarification_rate = clarification_count / total_messages * 100
            if clarification_rate > 10:
                insights.append(
                    f"High clarification rate: {clarification_rate:.1f}% of messages require follow-up"
                )
                recommendations.append(
                    "Experiment: Improve input parsing to reduce clarification requests"
                )

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "period_analyzed": "last 7 days",
            "insights": insights,
            "hypotheses": hypotheses,
            "recommendations": recommendations,
            "raw_summary": summary,
        }


# Global analytics collector instance
_analytics: AnalyticsCollector | None = None


def get_analytics() -> AnalyticsCollector:
    """Get the global analytics collector."""
    global _analytics
    if _analytics is None:
        _analytics = AnalyticsCollector()
    return _analytics


# Convenience functions for recording metrics
def record_tool_start(tool_name: str) -> float:
    """Record tool start time. Returns start time for duration calculation."""
    return time.time()


def record_tool_complete(
    tool_name: str,
    start_time: float,
    success: bool = True,
    error_code: ToolErrorCode | str | None = None,
    user_id: str | None = None,
    conversation_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record tool completion with duration."""
    duration_ms = int((time.time() - start_time) * 1000)
    get_analytics().record_tool_result(
        tool_name=tool_name,
        success=success,
        user_id=user_id,
        conversation_id=conversation_id,
        error_code=error_code,
        duration_ms=duration_ms,
        metadata=metadata,
    )
