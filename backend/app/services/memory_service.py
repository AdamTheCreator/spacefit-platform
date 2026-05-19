"""
Memory Service

Manages per-user memory that persists across chat sessions.
Used to personalize AI responses with context about the user's:
- Previously analyzed properties
- Book of business (tenant relationships)
- Inferred preferences
"""
import logging
from datetime import datetime
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user_memory import UserMemory

logger = logging.getLogger(__name__)


class MemoryService:
    """Service for managing user memory."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create(self, user_id: str) -> UserMemory:
        """Get existing memory or create a new one for the user."""
        result = await self.db.execute(
            select(UserMemory).where(UserMemory.user_id == user_id)
        )
        memory = result.scalar_one_or_none()

        if memory is None:
            memory = UserMemory(user_id=user_id)
            self.db.add(memory)
            await self.db.commit()
            await self.db.refresh(memory)
            logger.debug("Created new memory for user %s", user_id)

        return memory

    async def add_property_analysis(
        self,
        user_id: str,
        address: str,
        asset_type: str,
        key_findings: list[str],
        void_count: int = 0,
    ) -> UserMemory:
        """
        Record a property analysis in user memory.

        Args:
            user_id: User ID
            address: Property address
            asset_type: Type of property (e.g., "QSR pad", "Strip center")
            key_findings: List of key findings from the analysis
            void_count: Number of voids identified
        """
        memory = await self.get_or_create(user_id)

        # Create new property record
        property_record = {
            "address": address,
            "asset_type": asset_type,
            "analysis_date": datetime.utcnow().isoformat(),
            "key_findings": key_findings[:5],  # Keep top 5 findings
            "void_count": void_count,
        }

        # Append to analyzed properties (keep last 20)
        properties = list(memory.analyzed_properties or [])
        properties.insert(0, property_record)
        memory.analyzed_properties = properties[:20]

        # Increment total analyses
        memory.total_analyses = (memory.total_analyses or 0) + 1

        # Update inferred preferences based on analysis patterns
        await self._update_preferences_from_analysis(memory, asset_type, address)

        memory.last_updated = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(memory)

        logger.info("Added property analysis for user %s: %s", user_id, address)
        return memory

    async def _update_preferences_from_analysis(
        self, memory: UserMemory, asset_type: str, address: str
    ) -> None:
        """Update inferred preferences based on analysis patterns."""
        prefs = dict(memory.preferences or {})

        # Track preferred asset types
        asset_types = prefs.get("preferred_asset_types", [])
        if asset_type and asset_type not in asset_types:
            asset_types.append(asset_type)
        prefs["preferred_asset_types"] = asset_types[-10:]  # Keep last 10

        # Extract state/region from address for trade area preferences
        parts = address.split(",")
        if len(parts) >= 2:
            state = parts[-1].strip().split()[0] if parts[-1].strip() else ""
            if state and len(state) == 2:
                trade_areas = prefs.get("preferred_trade_areas", [])
                if state not in trade_areas:
                    trade_areas.append(state)
                prefs["preferred_trade_areas"] = trade_areas[-10:]

        memory.preferences = prefs

    async def update_book_of_business(
        self,
        user_id: str,
        tenant_data: list[dict],
    ) -> UserMemory:
        """
        Update book of business summary from imported customer data.

        Args:
            user_id: User ID
            tenant_data: List of tenant/customer records with fields like:
                - name, company_name, city, state, tags, criteria
        """
        memory = await self.get_or_create(user_id)

        # Analyze tenant data
        tenant_count = len(tenant_data)

        # Extract categories from tags/criteria
        categories: list[str] = []
        for tenant in tenant_data:
            tags = tenant.get("tags") or []
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",")]
            categories.extend(tags)

            criteria = tenant.get("criteria") or {}
            if isinstance(criteria, dict):
                cat = criteria.get("category") or criteria.get("type")
                if cat:
                    categories.append(cat)

        # Count categories and get top ones
        category_counts = Counter(categories)
        top_categories = [cat for cat, _ in category_counts.most_common(10)]

        # Extract coverage areas
        coverage_areas: list[str] = []
        for tenant in tenant_data:
            city = tenant.get("city")
            state = tenant.get("state")
            if city and state:
                coverage_areas.append(f"{city}, {state}")
            elif state:
                coverage_areas.append(state)

        area_counts = Counter(coverage_areas)
        top_areas = [area for area, _ in area_counts.most_common(10)]

        memory.book_of_business_summary = {
            "tenant_count": tenant_count,
            "top_categories": top_categories,
            "coverage_areas": top_areas,
            "last_import": datetime.utcnow().isoformat(),
        }

        memory.last_updated = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(memory)

        logger.info(
            "Updated book of business for user %s: %d tenants", user_id, tenant_count
        )
        return memory

    async def update_preferences(
        self,
        user_id: str,
        inferred_prefs: dict,
    ) -> UserMemory:
        """
        Update user preferences (can be called by the AI to remember patterns).

        Args:
            user_id: User ID
            inferred_prefs: Dict of preferences to merge, e.g.:
                - preferred_asset_types: list[str]
                - typical_sf_range: {min: int, max: int}
        """
        memory = await self.get_or_create(user_id)

        prefs = dict(memory.preferences or {})
        prefs.update(inferred_prefs)
        memory.preferences = prefs

        memory.last_updated = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(memory)

        return memory

    async def update_ai_summary(self, user_id: str, summary_text: str) -> UserMemory:
        """
        Update the AI-generated profile summary.

        Args:
            user_id: User ID
            summary_text: Text summary written by the AI
        """
        memory = await self.get_or_create(user_id)
        memory.ai_profile_summary = summary_text[:2000]  # Limit length
        memory.last_updated = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(memory)

        return memory

    async def get_context_block(self, user_id: str) -> str | None:
        """
        Generate a formatted context block for injection into the system prompt.

        Returns None if the user has no meaningful memory yet. Always
        attaches up to 10 most-recently-used approved personal facts
        when present, even if structured memory is empty.
        """
        from app.db.models.user_fact import UserFact

        result = await self.db.execute(
            select(UserMemory).where(UserMemory.user_id == user_id)
        )
        memory = result.scalar_one_or_none()

        # Pull approved facts in last-used-first order so the rolling
        # injection window stays fresh as the conversation evolves.
        fact_rows = (
            (
                await self.db.execute(
                    select(UserFact)
                    .where(
                        UserFact.user_id == user_id,
                        UserFact.status == "approved",
                    )
                    .order_by(
                        UserFact.last_used_at.desc().nulls_last(),
                        UserFact.approved_at.desc().nulls_last(),
                    )
                    .limit(10)
                )
            )
            .scalars()
            .all()
        )

        if memory is None and not fact_rows:
            return None

        has_analyses = bool(memory) and (memory.total_analyses or 0) > 0
        has_bob = bool(memory) and bool(
            (memory.book_of_business_summary or {}).get("tenant_count", 0)
        )
        has_prefs = bool(memory) and bool(memory.preferences)
        has_facts = bool(fact_rows)

        if not (has_analyses or has_bob or has_prefs or has_facts):
            return None

        if memory is None:
            # Synthesize an empty memory so the rest of the formatter
            # can use attribute access uniformly.
            class _Empty:
                analyzed_properties: list = []
                book_of_business_summary: dict = {}
                preferences: dict = {}
                total_analyses: int = 0

            memory = _Empty()  # type: ignore[assignment]

        lines = ["<user-memory>", "## What I Know About You"]

        # Summary stats
        if has_analyses:
            props = memory.analyzed_properties or []
            asset_types = memory.preferences.get("preferred_asset_types", [])
            regions = memory.preferences.get("preferred_trade_areas", [])

            type_str = ", ".join(asset_types[:3]) if asset_types else "various"
            region_str = ", ".join(regions[:3]) if regions else "multiple regions"

            lines.append(
                f"- You've analyzed {memory.total_analyses} properties, mostly {type_str} in {region_str}"
            )

        if has_bob:
            bob = memory.book_of_business_summary
            tenant_count = bob.get("tenant_count", 0)
            categories = bob.get("top_categories", [])
            cat_str = ", ".join(categories[:3]) if categories else "various categories"
            lines.append(
                f"- Your book of business has {tenant_count} tenants across {cat_str}"
            )

        prefs = memory.preferences or {}
        sf_range = prefs.get("typical_sf_range")
        if sf_range:
            lines.append(
                f"- You typically look at {sf_range.get('min', 0):,}-{sf_range.get('max', 0):,} SF spaces"
            )

        # Recent properties
        props = memory.analyzed_properties or []
        if props:
            lines.append("")
            lines.append("## Your Recent Properties")
            from datetime import datetime as dt

            for prop in props[:3]:
                addr = prop.get("address", "Unknown")
                asset = prop.get("asset_type", "Property")
                voids = prop.get("void_count", 0)
                date_str = prop.get("analysis_date", "")

                # Format date
                try:
                    d = dt.fromisoformat(date_str.replace("Z", "+00:00"))
                    date_fmt = d.strftime("%b %Y")
                except Exception:
                    date_fmt = "Recently"

                findings = prop.get("key_findings", [])
                finding_str = findings[0] if findings else f"{voids} voids identified"
                lines.append(f"- {addr} - {asset}, {finding_str} ({date_fmt})")

        # Top tenant categories
        if has_bob:
            bob = memory.book_of_business_summary
            categories = bob.get("top_categories", [])
            if categories:
                lines.append("")
                lines.append("## Your Top Tenant Categories")
                for cat in categories[:5]:
                    lines.append(f"- {cat}")

        if fact_rows:
            lines.append("")
            lines.append("## What you should remember about me")
            for fact in fact_rows:
                lines.append(f"- {fact.text}")
            # Bump last_used_at so the rolling window stays fresh.
            now = datetime.utcnow()
            for fact in fact_rows:
                fact.last_used_at = now
            try:
                await self.db.commit()
            except Exception:
                # Best-effort. Don't block prompt assembly on a write
                # failure (e.g. concurrent update from the approve endpoint).
                await self.db.rollback()

        lines.append("</user-memory>")

        return "\n".join(lines)

    async def clear_memory(self, user_id: str) -> bool:
        """Clear all memory for a user. Returns True if memory existed."""
        result = await self.db.execute(
            select(UserMemory).where(UserMemory.user_id == user_id)
        )
        memory = result.scalar_one_or_none()

        if memory:
            await self.db.delete(memory)
            await self.db.commit()
            logger.info("Cleared memory for user %s", user_id)
            return True

        return False


# Convenience function for getting the service
def get_memory_service(db: AsyncSession) -> MemoryService:
    return MemoryService(db)
