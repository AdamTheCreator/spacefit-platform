"""
Placer.ai Browser Agents - Browser-based agents for visitor traffic, customer profiles, and void analysis.

These agents use browser automation to scrape data from Placer.ai's web interface,
replacing the API-based approach which is cost-prohibitive.

Key data types:
- Visitor Traffic: Visitor counts, peak times, dwell time (mobile data on people visiting)
- Customer Profile: Actual visitor demographics (vs Census which is just residents)
- Void Analysis: Missing tenant categories with match scores
"""

from typing import Any

from app.agents.browser_agent import BrowserBasedAgent, BrowserProgressCallback
from app.models.chat import AgentType, Message, MessageRole
from app.services.browser.manager import BrowserManager
from app.scrapers import get_scraper
from app.scrapers.base import DataType
from app.core.security import decrypt_credential


class PlacerAIFootTrafficAgent(BrowserBasedAgent):
    """Browser-based agent that scrapes visitor traffic data from Placer.ai."""

    agent_type = AgentType.PLACER
    name = "Placer.ai Visitor Traffic"
    description = "Analyzes visitor traffic patterns using Placer.ai browser automation"

    is_browser_based = True
    typical_duration_seconds = 45

    def __init__(self, progress_callback: BrowserProgressCallback | None = None):
        super().__init__(progress_callback)

    @property
    def required_site(self) -> str:
        return "placer"

    @property
    def required_data_types(self) -> list[DataType]:
        return [DataType.VISITOR_TRAFFIC]

    async def can_handle(self, task: str) -> bool:
        """Can handle visitor traffic related tasks."""
        task_lower = task.lower()
        keywords = [
            "visitor traffic",
            "foot traffic",
            "visitors",
            "footfall",
            "visit",
            "dwell time",
            "peak hours",
            "peak times",
        ]
        return any(word in task_lower for word in keywords)

    async def _execute_with_browser(
        self,
        task: str,
        context: dict[str, Any],
    ) -> Message:
        """Execute visitor traffic scraping from Placer.ai."""
        address = context.get("address")
        user_id = context.get("user_id")
        credential = context.get("credential")

        if not address:
            return self._create_error_message("No address provided for foot traffic analysis.")

        manager = await BrowserManager.get_instance()
        scraper = get_scraper("placer", progress_callback=self._scraper_progress_adapter)

        async with manager.get_context(user_id, "placer") as browser_context:
            # Check if logged in
            self.report_progress("auth", 10, "Checking Placer.ai session...")

            if not await scraper.is_logged_in(browser_context):
                self.report_progress("auth", 15, "Logging in to Placer.ai...")

                try:
                    username = decrypt_credential(credential.username_encrypted)
                    password = decrypt_credential(credential.password_encrypted)
                except Exception as e:
                    return self._create_error_message(
                        f"Failed to decrypt credentials: {str(e)}"
                    )

                success = await scraper.login(browser_context, username, password)
                if not success:
                    return Message(
                        role=MessageRole.AGENT,
                        agent_type=self.agent_type,
                        content=(
                            "**Login Failed**\n\n"
                            "Could not log in to Placer.ai. Please verify your credentials "
                            "in Settings > Connections."
                        ),
                    )

            self.report_progress("scrape", 30, f"Searching for {address}...")

            # Scrape visitor traffic
            result = await scraper.scrape(
                browser_context,
                DataType.VISITOR_TRAFFIC,
                {"address": address},
            )

            if result.success:
                self.report_progress("complete", 100, "Visitor traffic data retrieved!")
                return Message(
                    role=MessageRole.AGENT,
                    agent_type=self.agent_type,
                    content=self._format_foot_traffic(result.data, address),
                )
            else:
                return self._create_error_message(
                    f"Could not retrieve foot traffic data: {result.error}"
                )

    def _format_foot_traffic(self, data: dict[str, Any], address: str) -> str:
        """Format visitor traffic data for display in chat."""
        venue_name = data.get("venue_name", address)

        lines = [
            f"## Visitor Traffic Analysis",
            f"**{venue_name}**",
            "",
            "### Visitor Volume",
        ]

        if data.get("monthly_visitors"):
            val = data["monthly_visitors"]
            lines.append(f"- **Monthly Visitors**: {val:,}" if isinstance(val, int) else f"- **Monthly Visitors**: {val}")

        if data.get("daily_avg_visitors"):
            val = data["daily_avg_visitors"]
            lines.append(f"- **Daily Average**: {val:,}" if isinstance(val, int) else f"- **Daily Average**: {val}")

        if data.get("vehicles_per_day"):
            val = data["vehicles_per_day"]
            lines.append(f"- **Vehicles Per Day (VPD)**: {val:,}" if isinstance(val, int) else f"- **VPD**: {val}")

        lines.append("")
        lines.append("### Peak Times")

        if data.get("peak_day"):
            lines.append(f"- **Busiest Day**: {data['peak_day']}")
        if data.get("peak_hour"):
            lines.append(f"- **Peak Hour**: {data['peak_hour']}")

        if data.get("year_over_year_change_pct") is not None:
            yoy = data["year_over_year_change_pct"]
            trend = "+" if yoy > 0 else ""
            lines.append(f"\n**Year-over-Year Change**: {trend}{yoy:.1f}%")

        if data.get("avg_dwell_time_minutes"):
            lines.append(f"**Avg. Dwell Time**: {data['avg_dwell_time_minutes']:.0f} minutes")

        if data.get("visitor_radius_miles"):
            lines.append(f"**Trade Area Radius**: {data['visitor_radius_miles']:.1f} miles")

        lines.append("")
        lines.append(f"*Source: {data.get('source', 'Placer.ai')}*")

        return "\n".join(lines)


class PlacerAICustomerProfileAgent(BrowserBasedAgent):
    """Browser-based agent that scrapes customer profile / audience data from Placer.ai."""

    agent_type = AgentType.PLACER
    name = "Placer.ai Customer Profile"
    description = "Analyzes actual visitor demographics using Placer.ai browser automation"

    is_browser_based = True
    typical_duration_seconds = 45

    def __init__(self, progress_callback: BrowserProgressCallback | None = None):
        super().__init__(progress_callback)

    @property
    def required_site(self) -> str:
        return "placer"

    @property
    def required_data_types(self) -> list[DataType]:
        return [DataType.CUSTOMER_PROFILE]

    async def can_handle(self, task: str) -> bool:
        """Can handle customer profile related tasks."""
        task_lower = task.lower()
        keywords = [
            "customer profile",
            "visitor demographics",
            "audience",
            "who visits",
            "customer demographics",
            "visitor profile",
            "shopper profile",
            "actual visitors",
        ]
        return any(word in task_lower for word in keywords)

    async def _execute_with_browser(
        self,
        task: str,
        context: dict[str, Any],
    ) -> Message:
        """Execute customer profile scraping from Placer.ai."""
        address = context.get("address")
        user_id = context.get("user_id")
        credential = context.get("credential")

        if not address:
            return self._create_error_message("No address provided for customer profile analysis.")

        manager = await BrowserManager.get_instance()
        scraper = get_scraper("placer", progress_callback=self._scraper_progress_adapter)

        async with manager.get_context(user_id, "placer") as browser_context:
            self.report_progress("auth", 10, "Checking Placer.ai session...")

            if not await scraper.is_logged_in(browser_context):
                self.report_progress("auth", 15, "Logging in to Placer.ai...")

                try:
                    username = decrypt_credential(credential.username_encrypted)
                    password = decrypt_credential(credential.password_encrypted)
                except Exception as e:
                    return self._create_error_message(
                        f"Failed to decrypt credentials: {str(e)}"
                    )

                success = await scraper.login(browser_context, username, password)
                if not success:
                    return Message(
                        role=MessageRole.AGENT,
                        agent_type=self.agent_type,
                        content=(
                            "**Login Failed**\n\n"
                            "Could not log in to Placer.ai. Please verify your credentials "
                            "in Settings > Connections."
                        ),
                    )

            self.report_progress("scrape", 30, f"Analyzing customers for {address}...")

            result = await scraper.scrape(
                browser_context,
                DataType.CUSTOMER_PROFILE,
                {"address": address},
            )

            if result.success:
                self.report_progress("complete", 100, "Customer profile retrieved!")
                return Message(
                    role=MessageRole.AGENT,
                    agent_type=self.agent_type,
                    content=self._format_customer_profile(result.data, address),
                )
            else:
                return self._create_error_message(
                    f"Could not retrieve customer profile: {result.error}"
                )

    def _format_customer_profile(self, data: dict[str, Any], address: str) -> str:
        """Format customer profile data for display in chat."""
        venue_name = data.get("venue_name", address)

        lines = [
            f"## Customer Profile",
            f"**{venue_name}**",
            "",
            "*Based on actual visitors (mobile data), not just nearby residents*",
            "",
            "### Visitor Demographics",
        ]

        if data.get("median_household_income"):
            val = data["median_household_income"]
            lines.append(f"- **Median HH Income**: ${val:,}" if isinstance(val, int) else f"- **Median HH Income**: {val}")

        if data.get("median_age"):
            lines.append(f"- **Median Age**: {data['median_age']:.1f} years")

        if data.get("bachelors_degree_pct"):
            pct = data["bachelors_degree_pct"]
            education = "Bachelor's degree or higher" if pct > 40 else "Some college"
            lines.append(f"- **Education**: {education} ({pct:.0f}% with degree)")

        if data.get("avg_household_size"):
            lines.append(f"- **Avg. Household Size**: {data['avg_household_size']:.1f}")

        # Gender split
        if data.get("male_pct") or data.get("female_pct"):
            lines.append("")
            lines.append("### Gender Split")
            if data.get("female_pct"):
                lines.append(f"- **Female**: {data['female_pct']:.0f}%")
            if data.get("male_pct"):
                lines.append(f"- **Male**: {data['male_pct']:.0f}%")

        # Age distribution
        age_fields = [
            ("age_18_24_pct", "18-24"),
            ("age_25_34_pct", "25-34"),
            ("age_35_44_pct", "35-44"),
            ("age_45_54_pct", "45-54"),
            ("age_55_plus_pct", "55+"),
        ]
        age_data = [(label, data.get(key)) for key, label in age_fields if data.get(key)]

        if age_data:
            lines.append("")
            lines.append("### Age Distribution")
            for label, pct in age_data:
                lines.append(f"- **{label}**: {pct:.0f}%")

        lines.append("")
        lines.append(f"*Source: {data.get('source', 'Placer.ai')}*")

        return "\n".join(lines)


class PlacerAIVoidAnalysisAgent(BrowserBasedAgent):
    """Browser-based agent that scrapes void analysis / missing tenants from Placer.ai."""

    agent_type = AgentType.VOID_ANALYSIS
    name = "Placer.ai Void Analysis"
    description = "Identifies missing tenant categories using Placer.ai browser automation"

    is_browser_based = True
    typical_duration_seconds = 50

    def __init__(self, progress_callback: BrowserProgressCallback | None = None):
        super().__init__(progress_callback)

    @property
    def required_site(self) -> str:
        return "placer"

    @property
    def required_data_types(self) -> list[DataType]:
        return [DataType.VOID_ANALYSIS]

    async def can_handle(self, task: str) -> bool:
        """Can handle void analysis related tasks."""
        task_lower = task.lower()
        keywords = [
            "void",
            "gap analysis",
            "missing tenants",
            "tenant opportunities",
            "what tenants",
            "who should",
            "tenant mix",
            "missing categories",
        ]
        return any(word in task_lower for word in keywords)

    async def _execute_with_browser(
        self,
        task: str,
        context: dict[str, Any],
    ) -> Message:
        """Execute void analysis scraping from Placer.ai."""
        address = context.get("address")
        user_id = context.get("user_id")
        credential = context.get("credential")

        if not address:
            return self._create_error_message("No address provided for void analysis.")

        manager = await BrowserManager.get_instance()
        scraper = get_scraper("placer", progress_callback=self._scraper_progress_adapter)

        async with manager.get_context(user_id, "placer") as browser_context:
            self.report_progress("auth", 10, "Checking Placer.ai session...")

            if not await scraper.is_logged_in(browser_context):
                self.report_progress("auth", 15, "Logging in to Placer.ai...")

                try:
                    username = decrypt_credential(credential.username_encrypted)
                    password = decrypt_credential(credential.password_encrypted)
                except Exception as e:
                    return self._create_error_message(
                        f"Failed to decrypt credentials: {str(e)}"
                    )

                success = await scraper.login(browser_context, username, password)
                if not success:
                    return Message(
                        role=MessageRole.AGENT,
                        agent_type=self.agent_type,
                        content=(
                            "**Login Failed**\n\n"
                            "Could not log in to Placer.ai. Please verify your credentials "
                            "in Settings > Connections."
                        ),
                    )

            self.report_progress("scrape", 30, f"Analyzing voids for {address}...")

            result = await scraper.scrape(
                browser_context,
                DataType.VOID_ANALYSIS,
                {"address": address},
            )

            if result.success:
                self.report_progress("complete", 100, "Void analysis complete!")
                return Message(
                    role=MessageRole.AGENT,
                    agent_type=self.agent_type,
                    content=self._format_void_analysis(result.data, address),
                )
            else:
                return self._create_error_message(
                    f"Could not retrieve void analysis: {result.error}"
                )

    def _format_void_analysis(self, data: dict[str, Any], address: str) -> str:
        """Format void analysis data for display in chat."""
        voids = data.get("voids", [])

        if not voids:
            return f"No void opportunities identified for {address}."

        lines = [
            f"## Void Analysis",
            f"**{address}**",
            "",
            "*Missing tenant categories based on customer profile match*",
            "",
        ]

        # Group voids by category
        categories: dict[str, list[dict]] = {}
        for void in voids:
            cat = void.get("category", "Other")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(void)

        # Sort categories by highest match score
        sorted_categories = sorted(
            categories.items(),
            key=lambda x: max((v.get("match_score") or 0) for v in x[1]),
            reverse=True,
        )

        for category, category_voids in sorted_categories:
            sorted_voids = sorted(
                category_voids,
                key=lambda x: x.get("match_score") or 0,
                reverse=True,
            )

            lines.append(f"### {category}")
            lines.append("| Tenant | Distance | Match Score |")
            lines.append("|--------|----------|-------------|")

            for void in sorted_voids:
                tenant = void.get("tenant_name", "Unknown")
                distance = (
                    f"{void['distance_miles']:.1f} mi"
                    if void.get("distance_miles")
                    else "Not in market"
                )
                score = f"{void['match_score']:.0f}%" if void.get("match_score") else "-"
                lines.append(f"| {tenant} | {distance} | {score} |")

            lines.append("")

        lines.append(f"*Source: {data.get('source', 'Placer.ai')}*")

        return "\n".join(lines)
