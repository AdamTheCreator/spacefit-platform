"""
SiteUSA Demographics Agent - Browser-based agent for demographics data.

This agent uses browser automation to scrape demographics data from SiteUSA.
It's slower than API-based agents but provides access to premium data.
"""

from typing import Any

from app.agents.browser_agent import BrowserBasedAgent, BrowserProgressCallback
from app.models.chat import AgentType, Message, MessageRole
from app.services.browser.manager import BrowserManager
from app.scrapers import get_scraper
from app.scrapers.base import DataType
from app.core.security import decrypt_credential


class SiteUSADemographicsAgent(BrowserBasedAgent):
    """Browser-based agent that scrapes demographics from SiteUSA."""

    agent_type = AgentType.DEMOGRAPHICS
    name = "SiteUSA Demographics"
    description = "Gathers demographics data from SiteUSA using browser automation"

    is_browser_based = True
    typical_duration_seconds = 45

    def __init__(self, progress_callback: BrowserProgressCallback | None = None):
        super().__init__(progress_callback)

    @property
    def required_site(self) -> str:
        return "siteusa"

    @property
    def required_data_types(self) -> list[DataType]:
        return [DataType.DEMOGRAPHICS]

    async def can_handle(self, task: str) -> bool:
        """Can handle demographic-related tasks."""
        task_lower = task.lower()
        keywords = [
            "demographic",
            "demographics",
            "population",
            "income",
            "census",
            "trade area",
            "households",
            "median age",
        ]
        return any(word in task_lower for word in keywords)

    async def _execute_with_browser(
        self,
        task: str,
        context: dict[str, Any],
    ) -> Message:
        """Execute demographics scraping."""
        address = context.get("address")
        radius_miles = context.get("radius_miles", 3)
        user_id = context.get("user_id")
        credential = context.get("credential")

        if not address:
            return self._create_error_message("No address provided for demographics analysis.")

        manager = await BrowserManager.get_instance()
        scraper = get_scraper("siteusa", progress_callback=self._scraper_progress_adapter)

        async with manager.get_context(user_id, "siteusa") as browser_context:
            # Check if logged in, re-login if needed
            self.report_progress("auth", 10, "Checking session status...")

            if not await scraper.is_logged_in(browser_context):
                self.report_progress("auth", 15, "Session expired, logging in...")

                try:
                    username = decrypt_credential(credential.username_encrypted)
                    password = decrypt_credential(credential.password_encrypted)
                except Exception as e:
                    return self._create_error_message(
                        f"Failed to decrypt credentials: {str(e)}"
                    )

                success = await scraper.login(browser_context, username, password)
                if not success:
                    return self._create_login_failed_message("SitesUSA")

            self.report_progress("scrape", 30, f"Searching for {address}...")

            # Scrape demographics
            result = await scraper.scrape(
                browser_context,
                DataType.DEMOGRAPHICS,
                {"address": address, "radius_miles": radius_miles},
            )

            if result.success:
                # Check for meaningful data before formatting
                meaningful_keys = [
                    "population", "households", "daytime_pop",
                    "median_income", "avg_income", "avg_age", "median_age",
                ]
                has_data = any(result.data.get(k) for k in meaningful_keys)

                if not has_data:
                    return self._create_empty_data_message(
                        "Demographics", address, "SitesUSA"
                    )

                self.report_progress("complete", 100, "Demographics retrieved!")
                return Message(
                    role=MessageRole.AGENT,
                    agent_type=self.agent_type,
                    content=self._format_demographics(result.data, address, radius_miles),
                )
            else:
                return self._create_error_message(
                    f"Could not retrieve demographics: {result.error}"
                )

    def _format_demographics(
        self,
        data: dict[str, Any],
        address: str,
        radius: float,
    ) -> str:
        """Format demographics data for display in chat."""
        lines = [
            f"## Trade Area Demographics",
            f"**{address}** ({radius}-mile radius)",
            "",
            "### Population & Households",
        ]

        if data.get("population"):
            pop = data["population"]
            if isinstance(pop, (int, float)):
                lines.append(f"- **Total Population**: {int(pop):,}")
            else:
                lines.append(f"- **Total Population**: {pop}")

        if data.get("households"):
            hh = data["households"]
            if isinstance(hh, (int, float)):
                lines.append(f"- **Households**: {int(hh):,}")
            else:
                lines.append(f"- **Households**: {hh}")

        if data.get("daytime_pop"):
            dp = data["daytime_pop"]
            if isinstance(dp, (int, float)):
                lines.append(f"- **Daytime Population**: {int(dp):,}")
            else:
                lines.append(f"- **Daytime Population**: {dp}")

        lines.append("")
        lines.append("### Income")

        if data.get("median_income"):
            mi = data["median_income"]
            if isinstance(mi, (int, float)):
                lines.append(f"- **Median HH Income**: ${int(mi):,}")
            else:
                lines.append(f"- **Median HH Income**: {mi}")

        if data.get("avg_income"):
            ai = data["avg_income"]
            if isinstance(ai, (int, float)):
                lines.append(f"- **Average HH Income**: ${int(ai):,}")
            else:
                lines.append(f"- **Average HH Income**: {ai}")

        if data.get("avg_age") or data.get("median_age"):
            lines.append("")
            lines.append("### Age")
            age = data.get("avg_age") or data.get("median_age")
            lines.append(f"- **Median Age**: {age}")

        lines.append("")
        lines.append(f"*Source: {data.get('source', 'SiteUSA')}*")

        return "\n".join(lines)


class SiteUSAVehicleTrafficAgent(BrowserBasedAgent):
    """Browser-based agent that scrapes vehicle traffic (VPD) data from SiteUSA."""

    agent_type = AgentType.SITEUSA
    name = "SiteUSA Vehicle Traffic"
    description = "Analyzes vehicle traffic (VPD) patterns using SiteUSA browser automation"

    is_browser_based = True
    typical_duration_seconds = 50

    @property
    def required_site(self) -> str:
        return "siteusa"

    @property
    def required_data_types(self) -> list[DataType]:
        return [DataType.VEHICLE_TRAFFIC]

    async def can_handle(self, task: str) -> bool:
        """Can handle vehicle traffic tasks."""
        task_lower = task.lower()
        keywords = [
            "vehicle traffic",
            "vpd",
            "vehicles per day",
            "car traffic",
            "road traffic",
            "traffic count",
        ]
        return any(word in task_lower for word in keywords)

    async def _execute_with_browser(
        self,
        task: str,
        context: dict[str, Any],
    ) -> Message:
        """Execute vehicle traffic scraping."""
        address = context.get("address")
        user_id = context.get("user_id")
        credential = context.get("credential")

        if not address:
            return self._create_error_message("No address provided for vehicle traffic analysis.")

        manager = await BrowserManager.get_instance()
        scraper = get_scraper("siteusa", progress_callback=self._scraper_progress_adapter)

        async with manager.get_context(user_id, "siteusa") as browser_context:
            # Check login status
            if not await scraper.is_logged_in(browser_context):
                self.report_progress("auth", 15, "Logging in to SiteUSA...")

                try:
                    username = decrypt_credential(credential.username_encrypted)
                    password = decrypt_credential(credential.password_encrypted)
                except Exception:
                    return self._create_login_failed_message("SitesUSA")

                if not await scraper.login(browser_context, username, password):
                    return self._create_login_failed_message("SitesUSA")

            self.report_progress("scrape", 30, "Analyzing vehicle traffic...")

            result = await scraper.scrape(
                browser_context,
                DataType.VEHICLE_TRAFFIC,
                {"address": address},
            )

            if result.success:
                # Check for meaningful data before formatting
                meaningful_keys = [
                    "primary_road_vpd", "secondary_road_vpd",
                    "intersection_vpd", "peak_hours",
                ]
                has_data = any(result.data.get(k) for k in meaningful_keys)

                if not has_data:
                    return self._create_empty_data_message(
                        "Vehicle Traffic", address, "SitesUSA"
                    )

                return Message(
                    role=MessageRole.AGENT,
                    agent_type=self.agent_type,
                    content=self._format_vehicle_traffic(result.data, address),
                )
            else:
                return self._create_error_message(
                    f"Could not retrieve vehicle traffic data: {result.error}"
                )

    def _format_vehicle_traffic(self, data: dict[str, Any], address: str) -> str:
        """Format vehicle traffic (VPD) data for display."""
        lines = [
            f"## Vehicle Traffic Analysis (VPD)",
            f"**{address}**",
            "",
        ]

        if data.get("primary_road_vpd"):
            lines.append(f"- **Primary Road VPD**: {data['primary_road_vpd']:,}")
        if data.get("secondary_road_vpd"):
            lines.append(f"- **Secondary Road VPD**: {data['secondary_road_vpd']:,}")
        if data.get("intersection_vpd"):
            lines.append(f"- **Intersection VPD**: {data['intersection_vpd']:,}")
        if data.get("peak_hours"):
            lines.append(f"- **Peak Hours**: {data['peak_hours']}")
        if data.get("weekend_increase"):
            lines.append(f"- **Weekend Increase**: {data['weekend_increase']}")

        lines.append("")
        lines.append(f"*Source: {data.get('source', 'SiteUSA')}*")

        return "\n".join(lines)
