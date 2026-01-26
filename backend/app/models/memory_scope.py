"""
Memory Scope Models

Defines scopes for memory and context to ensure proper isolation between conversations.
By default, conversations are strictly isolated (conversation scope).
User-level memory is opt-in and must be explicitly tagged.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime


class MemoryScope(str, Enum):
    """
    Memory scopes from most specific to most general.
    Default is CONVERSATION - strict isolation.
    """
    SESSION = "session"  # Ephemeral, cleared on disconnect
    CONVERSATION = "conversation"  # Default, persists in this chat only
    USER = "user"  # Cross-conversation, requires explicit opt-in


class ContextSource(str, Enum):
    """Source of context being injected into the conversation."""
    SYSTEM_INSTRUCTIONS = "system_instructions"  # Base system prompt
    USER_PREFERENCES = "user_preferences"  # From UserPreferences table
    CONVERSATION_HISTORY = "conversation_history"  # Messages in this chat
    USER_MEMORY = "user_memory"  # Cross-conversation memories (opt-in)
    TOOL_RESULT = "tool_result"  # Results from tool execution
    AGENT_INFERENCE = "agent_inference"  # Inferred by agent during session


@dataclass
class ScopedContext:
    """
    A piece of context with explicit scope and source tracking.
    Used for debugging and ensuring proper isolation.
    """
    content: str
    scope: MemoryScope
    source: ContextSource
    conversation_id: str | None = None
    user_id: str | None = None
    tenant_id: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "scope": self.scope.value,
            "source": self.source.value,
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": self.metadata,
        }


@dataclass
class ContextFilter:
    """
    Filter for retrieving scoped context.
    Used to enforce isolation rules.
    """
    tenant_id: str | None = None
    user_id: str | None = None
    conversation_id: str | None = None
    scopes: list[MemoryScope] = field(default_factory=lambda: [MemoryScope.CONVERSATION])
    sources: list[ContextSource] | None = None  # None = all sources

    def allows_scope(self, scope: MemoryScope) -> bool:
        """Check if a scope is allowed by this filter."""
        return scope in self.scopes

    def matches(self, context: ScopedContext) -> bool:
        """Check if a context item matches this filter."""
        # Always require matching tenant
        if self.tenant_id and context.tenant_id != self.tenant_id:
            return False

        # Always require matching user
        if self.user_id and context.user_id != self.user_id:
            return False

        # For conversation scope, require matching conversation_id
        if context.scope == MemoryScope.CONVERSATION:
            if self.conversation_id and context.conversation_id != self.conversation_id:
                return False

        # Check if scope is allowed
        if not self.allows_scope(context.scope):
            return False

        # Check source filter
        if self.sources and context.source not in self.sources:
            return False

        return True


@dataclass
class ConversationContext:
    """
    Complete context for a conversation, with explicit scope tracking.
    """
    conversation_id: str
    user_id: str
    tenant_id: str | None = None

    # System-level context (always included)
    system_instructions: str = ""

    # Conversation-scoped context (default)
    conversation_history: list[dict[str, str]] = field(default_factory=list)
    conversation_metadata: dict[str, Any] = field(default_factory=dict)

    # User-scoped context (opt-in only)
    user_preferences_context: str | None = None
    cross_conversation_enabled: bool = False

    # Tracking for debugging
    context_sources: list[ScopedContext] = field(default_factory=list)

    def get_full_system_prompt(self) -> str:
        """Build the full system prompt with proper scope annotations."""
        parts = [self.system_instructions]

        # Only include user preferences context if explicitly enabled
        if self.cross_conversation_enabled and self.user_preferences_context:
            parts.append("\n\n[USER CONTEXT - from preferences, may reference past conversations]")
            parts.append(self.user_preferences_context)

        return "\n".join(parts)

    def add_source(self, context: ScopedContext) -> None:
        """Track a context source for debugging."""
        self.context_sources.append(context)

    def get_debug_summary(self) -> dict[str, Any]:
        """Get a summary of context sources for debugging."""
        return {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "cross_conversation_enabled": self.cross_conversation_enabled,
            "message_count": len(self.conversation_history),
            "sources": [s.to_dict() for s in self.context_sources],
        }


# Feature flag for cross-conversation context
# Default: False (strict isolation)
ALLOW_CROSS_CONVERSATION_CONTEXT_DEFAULT = False


def should_include_user_context(
    feature_flag: bool | None = None,
    user_opt_in: bool = False,
) -> bool:
    """
    Determine if user-level context should be included.

    Cross-conversation context requires BOTH:
    1. Feature flag enabled (system level)
    2. User opt-in (user level)

    Args:
        feature_flag: System-level feature flag (None = use default)
        user_opt_in: Whether user has opted into cross-conversation context

    Returns:
        True if user context should be included
    """
    flag = feature_flag if feature_flag is not None else ALLOW_CROSS_CONVERSATION_CONTEXT_DEFAULT
    return flag and user_opt_in
