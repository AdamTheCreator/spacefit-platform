"""
Base class for browser-based agents.

Browser agents are slower than API agents and require special handling:
- Progress updates during execution
- Session management
- Error recovery
"""

from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional

from app.agents.base import BaseAgent
from app.models.chat import AgentType, Message, MessageRole
from app.scrapers.base import DataType, ProgressUpdate


@dataclass
class BrowserAgentProgress:
    """Progress update for browser agent tasks."""

    agent_type: AgentType
    step: str
    progress_pct: int  # 0-100
    message: str
    estimated_remaining_seconds: Optional[int] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


BrowserProgressCallback = Callable[[BrowserAgentProgress], None]


class BrowserBasedAgent(BaseAgent):
    """
    Base class for agents that use browser automation.

    Key differences from API-based agents:
    1. Much slower execution (30s - 2min typical)
    2. Requires user credentials
    3. Provides progress updates
    4. May require session refresh
    """

    # Class-level flag to identify browser-based agents
    is_browser_based: bool = True

    # Typical execution time in seconds
    typical_duration_seconds: int = 45

    def __init__(
        self,
        progress_callback: Optional[BrowserProgressCallback] = None,
    ):
        super().__init__()
        self.progress_callback = progress_callback

    @property
    @abstractmethod
    def required_site(self) -> str:
        """Site name that this agent requires credentials for (e.g., 'siteusa')."""
        pass

    @property
    @abstractmethod
    def required_data_types(self) -> list[DataType]:
        """Data types this agent needs to scrape."""
        pass

    def report_progress(
        self,
        step: str,
        progress_pct: int,
        message: str,
        estimated_remaining: Optional[int] = None,
    ) -> None:
        """Report progress to the callback."""
        if self.progress_callback:
            self.progress_callback(
                BrowserAgentProgress(
                    agent_type=self.agent_type,
                    step=step,
                    progress_pct=progress_pct,
                    message=message,
                    estimated_remaining_seconds=estimated_remaining,
                )
            )

    def _scraper_progress_adapter(self, update: ProgressUpdate) -> None:
        """Adapt scraper progress updates to agent progress updates."""
        self.report_progress(
            step=update.step,
            progress_pct=update.progress_pct,
            message=update.message,
        )

    async def execute(self, task: str, context: dict[str, Any]) -> Message:
        """
        Execute the browser-based agent task.

        Context should include:
        - user_id: User ID for session lookup
        - address: Address to analyze
        - credential: SiteCredential model instance (optional, will be fetched if not provided)
        - db: Database session for credential lookup
        """
        user_id = context.get("user_id")
        credential = context.get("credential")

        if not user_id:
            return Message(
                role=MessageRole.AGENT,
                agent_type=self.agent_type,
                content="Error: User ID is required for browser-based agents.",
            )

        if not credential:
            return Message(
                role=MessageRole.AGENT,
                agent_type=self.agent_type,
                content=(
                    f"No {self.required_site.title()} credentials configured. "
                    "Please add your credentials in Settings > Connections."
                ),
            )

        self.report_progress("init", 5, "Initializing browser session...")

        try:
            result = await self._execute_with_browser(task, context)
            return result
        except Exception as e:
            return Message(
                role=MessageRole.AGENT,
                agent_type=self.agent_type,
                content=f"Error executing browser task: {str(e)}",
            )

    @abstractmethod
    async def _execute_with_browser(
        self,
        task: str,
        context: dict[str, Any],
    ) -> Message:
        """Implement the actual browser-based logic."""
        pass

    def _create_error_message(self, error: str) -> Message:
        """Create a standardized error message."""
        return Message(
            role=MessageRole.AGENT,
            agent_type=self.agent_type,
            content=f"**Error**: {error}",
        )

    def _create_no_credentials_message(self) -> Message:
        """Create a message for missing credentials."""
        return Message(
            role=MessageRole.AGENT,
            agent_type=self.agent_type,
            content=(
                f"**{self.required_site.title()} Connection Required**\n\n"
                f"To use this analysis, please connect your {self.required_site.title()} account:\n"
                f"1. Go to **Settings > Connections**\n"
                f"2. Click **Connect** on {self.required_site.title()}\n"
                f"3. Enter your credentials\n\n"
                f"Your credentials are encrypted and stored securely."
            ),
        )

    # ------------------------------------------------------------------
    # Actionable failure messages
    # ------------------------------------------------------------------

    def _create_login_failed_message(self, site_display_name: str) -> Message:
        """Actionable message when automated login fails."""
        return Message(
            role=MessageRole.AGENT,
            agent_type=self.agent_type,
            content=(
                f"**{site_display_name} Connection Issue**\n\n"
                f"I was unable to log in to {site_display_name} to retrieve data. "
                "This usually means the session has expired or the saved credentials need updating.\n\n"
                "**To fix this:**\n"
                "1. Open **Connections** from the sidebar\n"
                f"2. Find **{site_display_name}** and click **Refresh Session**\n"
                "3. Complete the login (solve the CAPTCHA if prompted)\n"
                "4. Come back here and ask me again\n\n"
                "*Your data request has not been lost — just re-send your last message after reconnecting.*"
            ),
        )

    def _create_empty_data_message(
        self,
        data_type_label: str,
        address: str,
        site_display_name: str,
    ) -> Message:
        """Actionable message when the scraper returns success but no data."""
        return Message(
            role=MessageRole.AGENT,
            agent_type=self.agent_type,
            content=(
                f"**No {data_type_label} Found**\n\n"
                f"I connected to {site_display_name} successfully, but no "
                f"{data_type_label.lower()} data was returned for:\n"
                f"> {address}\n\n"
                "**Possible reasons:**\n"
                f"- {site_display_name} may not have coverage for this address\n"
                "- The address may need to be more specific (include city and state)\n"
                "- The property may not be in the database yet\n\n"
                "**What to try:**\n"
                "- Re-phrase with a more precise street address\n"
                "- Try a nearby major intersection instead\n"
                f"- Log in to {site_display_name} directly to confirm the property exists"
            ),
        )
