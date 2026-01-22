"""
CoStar Agents - Browser-based agents for CoStar data.

These agents use browser automation to scrape data from CoStar.
Slower than API-based agents but provides access to premium property data
including tenant rosters with lease details (rent PSF, expiration dates).
"""

from typing import Any

from app.agents.browser_agent import BrowserBasedAgent, BrowserProgressCallback
from app.models.chat import AgentType, Message, MessageRole
from app.services.browser.manager import BrowserManager
from app.scrapers import get_scraper
from app.scrapers.base import DataType
from app.scrapers.costar import format_tenant_roster
from app.core.security import decrypt_credential


class CoStarTenantAgent(BrowserBasedAgent):
    """
    Browser-based agent that scrapes tenant roster from CoStar.

    Provides premium tenant data including:
    - Tenant names and suites
    - Square footage per tenant
    - Lease type (NNN, Gross, etc.)
    - Rent per square foot
    - Lease expiration dates
    - Tenant categories
    """

    agent_type = AgentType.COSTAR
    name = "CoStar Tenants"
    description = "Retrieves tenant roster with lease details from CoStar"

    is_browser_based = True
    typical_duration_seconds = 60

    @property
    def required_site(self) -> str:
        return "costar"

    @property
    def required_data_types(self) -> list[DataType]:
        return [DataType.TENANT_DATA]

    async def can_handle(self, task: str) -> bool:
        """Check if this agent should handle the task."""
        task_lower = task.lower()
        # Trigger on CoStar-specific keywords or premium tenant data requests
        keywords = [
            "costar",
            "tenant roster",
            "lease details",
            "lease expiration",
            "rent psf",
            "rent per square foot",
            "tenant mix",
            "occupancy detail",
        ]
        return any(word in task_lower for word in keywords)

    async def execute(
        self,
        task: str,
        context: dict[str, Any],
    ) -> Message:
        """Execute tenant data scraping from CoStar."""
        address = context.get("address", "")
        user_id = context.get("user_id")
        credential = context.get("credential")

        if not address:
            return Message(
                role=MessageRole.AGENT,
                content="I need a property address to look up tenant data.",
                agent_type=self.agent_type,
            )

        if not credential:
            return Message(
                role=MessageRole.AGENT,
                content=(
                    "CoStar credentials are required to access tenant data. "
                    "Please add your CoStar login in Settings > Connections."
                ),
                agent_type=self.agent_type,
            )

        try:
            self.report_progress("init", 5, "Initializing CoStar connection...")

            # Get browser manager
            browser_manager = BrowserManager()

            # Get CoStar scraper
            scraper = get_scraper("costar", progress_callback=self._scraper_progress_adapter)

            self.report_progress("browser", 10, "Starting browser session...")

            # Get browser context
            browser_context = await browser_manager.get_context(user_id)

            # Check if already logged in
            self.report_progress("login", 15, "Checking login status...")
            is_logged_in = await scraper.is_logged_in(browser_context)

            if not is_logged_in:
                self.report_progress("login", 20, "Logging into CoStar...")

                # Decrypt credentials
                username = decrypt_credential(credential.username_encrypted)
                password = decrypt_credential(credential.password_encrypted)

                login_success = await scraper.login(browser_context, username, password)

                if not login_success:
                    return Message(
                        role=MessageRole.AGENT,
                        content=(
                            "Unable to log into CoStar. Please check your credentials "
                            "in Settings > Connections and try again."
                        ),
                        agent_type=self.agent_type,
                    )

            self.report_progress("scrape", 40, f"Searching for {address}...")

            # Scrape tenant data
            result = await scraper.scrape(
                browser_context,
                DataType.TENANT_DATA,
                {"address": address},
            )

            if not result.success:
                return Message(
                    role=MessageRole.AGENT,
                    content=f"Unable to retrieve tenant data: {result.error}",
                    agent_type=self.agent_type,
                )

            self.report_progress("format", 90, "Formatting tenant roster...")

            # Format the results
            formatted_output = format_tenant_roster(result.data, address)

            self.report_progress("complete", 100, "Tenant data retrieved")

            return Message(
                role=MessageRole.AGENT,
                content=formatted_output,
                agent_type=self.agent_type,
            )

        except Exception as e:
            return Message(
                role=MessageRole.AGENT,
                content=f"Error retrieving tenant data from CoStar: {str(e)}",
                agent_type=self.agent_type,
            )


class CoStarPropertyAgent(BrowserBasedAgent):
    """
    Browser-based agent for CoStar property details.

    Provides property information including:
    - Building details (year built, SF, floors)
    - Ownership information
    - Sale history
    - Parking and lot size
    """

    agent_type = AgentType.COSTAR
    name = "CoStar Property"
    description = "Retrieves property details from CoStar"

    is_browser_based = True
    typical_duration_seconds = 45

    @property
    def required_site(self) -> str:
        return "costar"

    @property
    def required_data_types(self) -> list[DataType]:
        return [DataType.PROPERTY_INFO]

    async def can_handle(self, task: str) -> bool:
        """Check if this agent should handle the task."""
        task_lower = task.lower()
        keywords = [
            "property info",
            "property details",
            "building info",
            "owner",
            "sale history",
            "costar property",
        ]
        return any(word in task_lower for word in keywords)

    async def execute(
        self,
        task: str,
        context: dict[str, Any],
    ) -> Message:
        """Execute property info scraping from CoStar."""
        address = context.get("address", "")
        user_id = context.get("user_id")
        credential = context.get("credential")

        if not address:
            return Message(
                role=MessageRole.AGENT,
                content="I need a property address to look up property details.",
                agent_type=self.agent_type,
            )

        if not credential:
            return Message(
                role=MessageRole.AGENT,
                content=(
                    "CoStar credentials are required to access property data. "
                    "Please add your CoStar login in Settings > Connections."
                ),
                agent_type=self.agent_type,
            )

        try:
            self.report_progress("init", 5, "Initializing CoStar connection...")

            browser_manager = BrowserManager()
            scraper = get_scraper("costar", progress_callback=self._scraper_progress_adapter)

            self.report_progress("browser", 10, "Starting browser session...")

            browser_context = await browser_manager.get_context(user_id)

            self.report_progress("login", 15, "Checking login status...")
            is_logged_in = await scraper.is_logged_in(browser_context)

            if not is_logged_in:
                self.report_progress("login", 20, "Logging into CoStar...")

                username = decrypt_credential(credential.username_encrypted)
                password = decrypt_credential(credential.password_encrypted)

                login_success = await scraper.login(browser_context, username, password)

                if not login_success:
                    return Message(
                        role=MessageRole.AGENT,
                        content="Unable to log into CoStar. Please check your credentials.",
                        agent_type=self.agent_type,
                    )

            self.report_progress("scrape", 40, f"Looking up property: {address}...")

            result = await scraper.scrape(
                browser_context,
                DataType.PROPERTY_INFO,
                {"address": address},
            )

            if not result.success:
                return Message(
                    role=MessageRole.AGENT,
                    content=f"Unable to retrieve property info: {result.error}",
                    agent_type=self.agent_type,
                )

            self.report_progress("format", 90, "Formatting property details...")

            # Format property info
            data = result.data
            lines = [
                f"**Property Details for {data.get('name', address)}**\n",
                f"*{address}*\n",
            ]

            if data.get("property_type"):
                lines.append(f"**Property Type:** {data['property_type']}")
            if data.get("year_built"):
                lines.append(f"**Year Built:** {data['year_built']}")
            if data.get("total_sqft"):
                lines.append(f"**Total SF:** {data['total_sqft']}")
            if data.get("floors"):
                lines.append(f"**Floors:** {data['floors']}")
            if data.get("parking_spaces"):
                lines.append(f"**Parking:** {data['parking_spaces']} spaces")
            if data.get("lot_size"):
                lines.append(f"**Lot Size:** {data['lot_size']}")

            if data.get("owner"):
                lines.append(f"\n**Owner:** {data['owner']}")

            if data.get("last_sale_date") or data.get("last_sale_price"):
                lines.append("\n**Sale History:**")
                if data.get("last_sale_date"):
                    lines.append(f"- Last Sale Date: {data['last_sale_date']}")
                if data.get("last_sale_price"):
                    lines.append(f"- Last Sale Price: {data['last_sale_price']}")

            if data.get("occupancy"):
                lines.append(f"\n**Occupancy:** {data['occupancy']}")

            lines.append("\n*Source: CoStar*")

            self.report_progress("complete", 100, "Property details retrieved")

            return Message(
                role=MessageRole.AGENT,
                content="\n".join(lines),
                agent_type=self.agent_type,
            )

        except Exception as e:
            return Message(
                role=MessageRole.AGENT,
                content=f"Error retrieving property data from CoStar: {str(e)}",
                agent_type=self.agent_type,
            )
