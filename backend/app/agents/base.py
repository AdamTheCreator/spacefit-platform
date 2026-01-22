from abc import ABC, abstractmethod
from typing import Any, Optional

from app.models.chat import AgentType, Message


class BaseAgent(ABC):
    """Base class for all SpaceFit agents."""

    agent_type: AgentType
    name: str
    description: str

    def __init__(self) -> None:
        self._browser_context: Optional[Any] = None

    @abstractmethod
    async def execute(self, task: str, context: dict[str, Any]) -> Message:
        """Execute the agent's primary task."""
        pass

    @abstractmethod
    async def can_handle(self, task: str) -> bool:
        """Determine if this agent can handle the given task."""
        pass

    async def initialize_browser(self, credentials: dict[str, str]) -> None:
        """Initialize browser automation with user credentials."""
        # TODO: Implement Playwright browser initialization
        pass

    async def cleanup(self) -> None:
        """Clean up resources (browser contexts, etc.)."""
        if self._browser_context:
            await self._browser_context.close()
