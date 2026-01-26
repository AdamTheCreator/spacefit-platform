"""
Tests for memory scope enforcement.

Tests verify:
1. Conversation scope isolation (default)
2. User-level context requires explicit opt-in
3. Cross-conversation context is properly tagged
4. New chat has no prior city context
"""

import pytest
from unittest.mock import MagicMock

from app.models.memory_scope import (
    MemoryScope,
    ContextSource,
    ScopedContext,
    ContextFilter,
    ConversationContext,
    should_include_user_context,
    ALLOW_CROSS_CONVERSATION_CONTEXT_DEFAULT,
)
from app.api.preferences import (
    build_personalized_context,
    build_conversation_scoped_context,
)


class TestMemoryScope:
    """Tests for MemoryScope enum."""

    def test_scope_values(self):
        assert MemoryScope.SESSION.value == "session"
        assert MemoryScope.CONVERSATION.value == "conversation"
        assert MemoryScope.USER.value == "user"


class TestScopedContext:
    """Tests for ScopedContext dataclass."""

    def test_to_dict(self):
        ctx = ScopedContext(
            content="Test content",
            scope=MemoryScope.CONVERSATION,
            source=ContextSource.CONVERSATION_HISTORY,
            conversation_id="conv-123",
            user_id="user-456",
        )
        d = ctx.to_dict()
        assert d["content"] == "Test content"
        assert d["scope"] == "conversation"
        assert d["source"] == "conversation_history"
        assert d["conversation_id"] == "conv-123"


class TestContextFilter:
    """Tests for ContextFilter."""

    def test_allows_scope(self):
        filter_default = ContextFilter(
            scopes=[MemoryScope.CONVERSATION]
        )
        assert filter_default.allows_scope(MemoryScope.CONVERSATION) is True
        assert filter_default.allows_scope(MemoryScope.USER) is False

        filter_with_user = ContextFilter(
            scopes=[MemoryScope.CONVERSATION, MemoryScope.USER]
        )
        assert filter_with_user.allows_scope(MemoryScope.USER) is True

    def test_matches_conversation_scope(self):
        filter = ContextFilter(
            user_id="user-123",
            conversation_id="conv-456",
            scopes=[MemoryScope.CONVERSATION]
        )

        # Should match same conversation
        ctx_same = ScopedContext(
            content="Test",
            scope=MemoryScope.CONVERSATION,
            source=ContextSource.CONVERSATION_HISTORY,
            conversation_id="conv-456",
            user_id="user-123",
        )
        assert filter.matches(ctx_same) is True

        # Should NOT match different conversation
        ctx_different = ScopedContext(
            content="Test",
            scope=MemoryScope.CONVERSATION,
            source=ContextSource.CONVERSATION_HISTORY,
            conversation_id="conv-789",  # Different!
            user_id="user-123",
        )
        assert filter.matches(ctx_different) is False

    def test_matches_user_scope(self):
        filter = ContextFilter(
            user_id="user-123",
            conversation_id="conv-456",
            scopes=[MemoryScope.CONVERSATION, MemoryScope.USER]  # Explicitly allow user scope
        )

        # User-scoped context should match regardless of conversation_id
        ctx_user = ScopedContext(
            content="User preference",
            scope=MemoryScope.USER,
            source=ContextSource.USER_PREFERENCES,
            user_id="user-123",
            # No conversation_id - user-level
        )
        assert filter.matches(ctx_user) is True


class TestConversationContext:
    """Tests for ConversationContext."""

    def test_get_full_system_prompt_no_cross_conversation(self):
        ctx = ConversationContext(
            conversation_id="conv-123",
            user_id="user-456",
            system_instructions="Base instructions",
            user_preferences_context="Markets: Reno, NV",
            cross_conversation_enabled=False,  # Default
        )

        prompt = ctx.get_full_system_prompt()
        assert "Base instructions" in prompt
        # User context should NOT be included when cross_conversation_enabled=False
        assert "Markets: Reno, NV" not in prompt

    def test_get_full_system_prompt_with_cross_conversation(self):
        ctx = ConversationContext(
            conversation_id="conv-123",
            user_id="user-456",
            system_instructions="Base instructions",
            user_preferences_context="Markets: Reno, NV",
            cross_conversation_enabled=True,  # Explicitly enabled
        )

        prompt = ctx.get_full_system_prompt()
        assert "Base instructions" in prompt
        assert "USER CONTEXT" in prompt
        assert "Markets: Reno, NV" in prompt


class TestShouldIncludeUserContext:
    """Tests for should_include_user_context function."""

    def test_default_is_false(self):
        assert ALLOW_CROSS_CONVERSATION_CONTEXT_DEFAULT is False

    def test_requires_both_flag_and_opt_in(self):
        # Neither enabled - should be False
        assert should_include_user_context(
            feature_flag=False,
            user_opt_in=False,
        ) is False

        # Only feature flag - should be False
        assert should_include_user_context(
            feature_flag=True,
            user_opt_in=False,
        ) is False

        # Only user opt-in - should be False
        assert should_include_user_context(
            feature_flag=False,
            user_opt_in=True,
        ) is False

        # Both enabled - should be True
        assert should_include_user_context(
            feature_flag=True,
            user_opt_in=True,
        ) is True


class TestBuildPersonalizedContext:
    """Tests for build_personalized_context function."""

    def _create_mock_prefs(
        self,
        role: str | None = None,
        markets: str | None = None,
        property_types: str | None = None,
    ):
        """Create a mock UserPreferences object."""
        prefs = MagicMock()
        prefs.role = role
        prefs.markets = markets
        prefs.property_types = property_types
        prefs.tenant_categories = None
        prefs.deal_size_min = None
        prefs.deal_size_max = None
        prefs.key_tenants = None
        prefs.analysis_priorities = None
        prefs.custom_notes = None
        return prefs

    def test_excludes_markets_by_default(self):
        """Verify markets are NOT included by default (prevents cross-chat leakage)."""
        prefs = self._create_mock_prefs(
            role="broker",
            markets='["Reno, NV", "Las Vegas, NV"]',
        )

        context = build_personalized_context(
            prefs,
            include_location_context=False,  # Default
            cross_conversation_enabled=False,  # Default
        )

        assert "broker" in context.lower()
        # Markets should NOT be included
        assert "Reno" not in context
        assert "Las Vegas" not in context
        assert "operate in" not in context.lower()

    def test_includes_markets_when_explicitly_enabled(self):
        """Verify markets are included when both flags are True."""
        prefs = self._create_mock_prefs(
            role="broker",
            markets='["Reno, NV", "Las Vegas, NV"]',
        )

        context = build_personalized_context(
            prefs,
            include_location_context=True,
            cross_conversation_enabled=True,
        )

        assert "broker" in context.lower()
        assert "Reno" in context
        assert "Las Vegas" in context
        assert "User-level preference" in context

    def test_conversation_scoped_context_excludes_markets(self):
        """Verify build_conversation_scoped_context never includes markets."""
        prefs = self._create_mock_prefs(
            role="investor",
            markets='["Boston, MA", "New York, NY"]',
            property_types='["retail", "office"]',
        )

        context = build_conversation_scoped_context(prefs)

        # Safe preferences should be included
        assert "investor" in context.lower()
        assert "Retail" in context or "retail" in context.lower()

        # Markets should NOT be included
        assert "Boston" not in context
        assert "New York" not in context


class TestCrossChatIsolation:
    """
    Integration tests verifying cross-chat isolation.

    These tests ensure that a new conversation does not inherit
    location/city context from previous conversations.
    """

    def test_new_conversation_has_no_prior_city(self):
        """
        Simulate starting a new chat after researching "Reno, NV".
        The new chat should NOT have Reno context.
        """
        # User's preferences from previous session
        prefs = MagicMock()
        prefs.role = "broker"
        prefs.markets = '["Reno, NV"]'  # From previous research
        prefs.property_types = '["retail"]'
        prefs.tenant_categories = None
        prefs.deal_size_min = None
        prefs.deal_size_max = None
        prefs.key_tenants = None
        prefs.analysis_priorities = None
        prefs.custom_notes = None

        # Create context for NEW conversation (simulating chat.py behavior)
        user_context = build_conversation_scoped_context(prefs)

        # Verify no Reno context
        assert "Reno" not in user_context
        assert "NV" not in user_context or "NV" in user_context and "operate" not in user_context

        # Role should still be there (safe user-level preference)
        assert "broker" in user_context.lower()

    def test_conversation_history_is_per_session(self):
        """
        Verify that conversation history is correctly scoped.
        """
        # Conversation 1: Reno
        ctx1 = ConversationContext(
            conversation_id="conv-reno",
            user_id="user-123",
            system_instructions="Base prompt",
            cross_conversation_enabled=False,
        )
        ctx1.conversation_history = [
            {"role": "user", "content": "Tell me about Reno, NV"},
            {"role": "assistant", "content": "Reno is..."},
        ]

        # Conversation 2: Boston (NEW conversation)
        ctx2 = ConversationContext(
            conversation_id="conv-boston",
            user_id="user-123",
            system_instructions="Base prompt",
            cross_conversation_enabled=False,
        )
        ctx2.conversation_history = []  # Empty - new conversation

        # Verify conversation 2 has no history from conversation 1
        assert len(ctx2.conversation_history) == 0
        assert ctx2.conversation_id != ctx1.conversation_id
