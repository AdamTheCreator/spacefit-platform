"""
Owner / Title Lookup Service

Provides ownership and title lookup via the ATTOM Data API.
Currently a stub that raises NotImplementedError until an ATTOM API key
is configured.
"""

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models.deal import Property

logger = logging.getLogger(__name__)


@dataclass
class OwnershipRecord:
    """Ownership and title information for a property."""

    owner_name: str
    owner_entity: str
    acquisition_date: str | None = None
    acquisition_price: float | None = None
    tax_assessment: float | None = None
    source: str = "attom"


async def lookup_owner_attom(
    address: str,
    city: str,
    state: str,
    zip_code: str,
) -> OwnershipRecord:
    """
    Look up property ownership via the ATTOM Data API.

    Args:
        address: Street address of the property.
        city: City name.
        state: Two-letter state code.
        zip_code: ZIP code.

    Returns:
        OwnershipRecord with owner information.

    Raises:
        NotImplementedError: ATTOM API key is required. Configure
            ATTOM_API_KEY in your .env file and sign up at
            https://api.gateway.attomdata.com to obtain a key.
    """
    raise NotImplementedError(
        "ATTOM API key is required for owner/title lookup. "
        "Set ATTOM_API_KEY in your .env file. "
        "Sign up at https://api.gateway.attomdata.com to obtain an API key."
    )


async def save_owner_to_property(
    property_id: str,
    record: OwnershipRecord,
    db: AsyncSession,
) -> None:
    """
    Save ownership information to an existing Property record.

    Updates the owner_name and owner_entity fields on the Property.

    Args:
        property_id: The ID of the Property to update.
        record: OwnershipRecord with the ownership data.
        db: Async database session.

    Raises:
        ValueError: If the property is not found.
    """
    result = await db.execute(
        select(Property).where(Property.id == property_id)
    )
    prop = result.scalar_one_or_none()

    if not prop:
        raise ValueError(f"Property {property_id} not found")

    prop.owner_name = record.owner_name
    prop.owner_entity = record.owner_entity

    await db.commit()

    logger.info(
        "[title_lookup] Saved owner info for property %s: %s (%s)",
        property_id,
        record.owner_name,
        record.owner_entity,
    )
