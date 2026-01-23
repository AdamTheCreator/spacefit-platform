"""
User Preferences API

Endpoints for managing user preferences that personalize the AI assistant.
"""

import json
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, CurrentUser
from app.db.models.credential import UserPreferences

router = APIRouter(prefix="/preferences", tags=["preferences"])


# Pydantic models
class PreferencesUpdate(BaseModel):
    """Request model for updating preferences."""
    role: str | None = Field(None, description="Professional role: broker, landlord, investor, developer, analyst")
    property_types: list[str] | None = Field(None, description="Property types: retail, industrial, office, mixed_use")
    tenant_categories: list[str] | None = Field(None, description="Tenant categories: qsr, fitness, medical, etc.")
    markets: list[str] | None = Field(None, description="Geographic markets")
    deal_size_min: int | None = Field(None, description="Minimum deal size in SF")
    deal_size_max: int | None = Field(None, description="Maximum deal size in SF")
    key_tenants: list[str] | None = Field(None, description="Key tenant relationships")
    analysis_priorities: list[str] | None = Field(None, description="Analysis priorities")
    custom_notes: str | None = Field(None, description="Additional context notes")


class PreferencesResponse(BaseModel):
    """Response model for preferences."""
    id: str
    role: str | None
    property_types: list[str]
    tenant_categories: list[str]
    markets: list[str]
    deal_size_min: int | None
    deal_size_max: int | None
    key_tenants: list[str]
    analysis_priorities: list[str]
    custom_notes: str | None
    is_complete: bool
    completion_percentage: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PreferencesOptionsResponse(BaseModel):
    """Available options for preference fields."""
    roles: list[dict[str, str]]
    property_types: list[dict[str, str]]
    tenant_categories: list[dict[str, str]]
    analysis_priorities: list[dict[str, str]]


# Predefined options
ROLE_OPTIONS = [
    {"value": "broker", "label": "Broker / Agent", "description": "Representing tenants or landlords in lease transactions"},
    {"value": "landlord", "label": "Landlord / Owner", "description": "Own and manage commercial properties"},
    {"value": "investor", "label": "Investor", "description": "Acquiring and investing in commercial real estate"},
    {"value": "developer", "label": "Developer", "description": "Developing new commercial properties"},
    {"value": "analyst", "label": "Analyst / Researcher", "description": "Analyzing market trends and opportunities"},
]

PROPERTY_TYPE_OPTIONS = [
    {"value": "retail", "label": "Retail", "description": "Shopping centers, strip malls, standalone retail"},
    {"value": "industrial", "label": "Industrial", "description": "Warehouses, distribution, manufacturing"},
    {"value": "office", "label": "Office", "description": "Office buildings and business parks"},
    {"value": "mixed_use", "label": "Mixed-Use", "description": "Combined retail, office, residential"},
    {"value": "multifamily", "label": "Multifamily", "description": "Apartment complexes and residential"},
]

TENANT_CATEGORY_OPTIONS = [
    {"value": "qsr", "label": "QSR / Fast Food", "description": "Quick service restaurants, drive-thrus"},
    {"value": "casual_dining", "label": "Casual Dining", "description": "Sit-down restaurants"},
    {"value": "fast_casual", "label": "Fast Casual", "description": "Chipotle, Panera, CAVA style"},
    {"value": "fitness", "label": "Fitness & Gyms", "description": "Planet Fitness, Orangetheory, etc."},
    {"value": "medical", "label": "Medical / Urgent Care", "description": "Medical offices, urgent care, dental"},
    {"value": "apparel", "label": "Apparel & Fashion", "description": "Clothing and accessories retail"},
    {"value": "grocery", "label": "Grocery", "description": "Supermarkets and specialty grocers"},
    {"value": "convenience", "label": "Convenience / Gas", "description": "C-stores, gas stations"},
    {"value": "banking", "label": "Banking & Financial", "description": "Banks, credit unions, financial services"},
    {"value": "beauty", "label": "Beauty & Personal Care", "description": "Salons, spas, beauty retail"},
    {"value": "entertainment", "label": "Entertainment", "description": "Movie theaters, bowling, arcades"},
    {"value": "discount", "label": "Discount / Dollar", "description": "Dollar stores, discount retailers"},
    {"value": "auto", "label": "Auto Services", "description": "Auto repair, oil change, car wash"},
    {"value": "pet", "label": "Pet Services", "description": "Pet stores, grooming, vet"},
    {"value": "coffee", "label": "Coffee & Beverage", "description": "Coffee shops, juice bars, boba"},
]

ANALYSIS_PRIORITY_OPTIONS = [
    {"value": "traffic_counts", "label": "Traffic Counts", "description": "Vehicle and pedestrian traffic data"},
    {"value": "demographics", "label": "Demographics", "description": "Population, income, age data"},
    {"value": "void_analysis", "label": "Void Analysis", "description": "Missing tenant opportunities"},
    {"value": "competition", "label": "Competition Analysis", "description": "Nearby competing tenants"},
    {"value": "visibility", "label": "Visibility & Access", "description": "Signage, parking, accessibility"},
    {"value": "co_tenancy", "label": "Co-Tenancy", "description": "Complementary tenant mix"},
]


def _parse_json_field(value: str | None) -> list[str]:
    """Parse a JSON string field into a list."""
    if not value:
        return []
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []


def _serialize_json_field(value: list[str] | None) -> str:
    """Serialize a list to JSON string."""
    if not value:
        return "[]"
    return json.dumps(value)


def _calculate_completion(prefs: UserPreferences) -> int:
    """Calculate profile completion percentage."""
    fields = [
        prefs.role is not None,
        len(_parse_json_field(prefs.property_types)) > 0,
        len(_parse_json_field(prefs.tenant_categories)) > 0,
        len(_parse_json_field(prefs.markets)) > 0,
    ]
    completed = sum(fields)
    return int((completed / len(fields)) * 100)


@router.get("/options", response_model=PreferencesOptionsResponse)
async def get_preference_options() -> PreferencesOptionsResponse:
    """Get available options for preference fields."""
    return PreferencesOptionsResponse(
        roles=ROLE_OPTIONS,
        property_types=PROPERTY_TYPE_OPTIONS,
        tenant_categories=TENANT_CATEGORY_OPTIONS,
        analysis_priorities=ANALYSIS_PRIORITY_OPTIONS,
    )


@router.get("", response_model=PreferencesResponse)
async def get_preferences(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PreferencesResponse:
    """Get current user's preferences."""
    result = await db.execute(
        select(UserPreferences).where(UserPreferences.user_id == current_user.id)
    )
    prefs = result.scalar_one_or_none()

    if not prefs:
        # Create default preferences
        prefs = UserPreferences(user_id=current_user.id)
        db.add(prefs)
        await db.commit()
        await db.refresh(prefs)

    return PreferencesResponse(
        id=prefs.id,
        role=prefs.role,
        property_types=_parse_json_field(prefs.property_types),
        tenant_categories=_parse_json_field(prefs.tenant_categories),
        markets=_parse_json_field(prefs.markets),
        deal_size_min=prefs.deal_size_min,
        deal_size_max=prefs.deal_size_max,
        key_tenants=_parse_json_field(prefs.key_tenants),
        analysis_priorities=_parse_json_field(prefs.analysis_priorities),
        custom_notes=prefs.custom_notes,
        is_complete=prefs.is_complete,
        completion_percentage=_calculate_completion(prefs),
        created_at=prefs.created_at,
        updated_at=prefs.updated_at,
    )


@router.put("", response_model=PreferencesResponse)
async def update_preferences(
    updates: PreferencesUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PreferencesResponse:
    """Update user preferences."""
    result = await db.execute(
        select(UserPreferences).where(UserPreferences.user_id == current_user.id)
    )
    prefs = result.scalar_one_or_none()

    if not prefs:
        prefs = UserPreferences(user_id=current_user.id)
        db.add(prefs)

    # Update fields if provided
    if updates.role is not None:
        prefs.role = updates.role
    if updates.property_types is not None:
        prefs.property_types = _serialize_json_field(updates.property_types)
    if updates.tenant_categories is not None:
        prefs.tenant_categories = _serialize_json_field(updates.tenant_categories)
    if updates.markets is not None:
        prefs.markets = _serialize_json_field(updates.markets)
    if updates.deal_size_min is not None:
        prefs.deal_size_min = updates.deal_size_min
    if updates.deal_size_max is not None:
        prefs.deal_size_max = updates.deal_size_max
    if updates.key_tenants is not None:
        prefs.key_tenants = _serialize_json_field(updates.key_tenants)
    if updates.analysis_priorities is not None:
        prefs.analysis_priorities = _serialize_json_field(updates.analysis_priorities)
    if updates.custom_notes is not None:
        prefs.custom_notes = updates.custom_notes

    # Check if profile is now complete
    completion = _calculate_completion(prefs)
    if completion >= 75 and not prefs.is_complete:
        prefs.is_complete = True
        prefs.completed_at = datetime.utcnow()

    await db.commit()
    await db.refresh(prefs)

    return PreferencesResponse(
        id=prefs.id,
        role=prefs.role,
        property_types=_parse_json_field(prefs.property_types),
        tenant_categories=_parse_json_field(prefs.tenant_categories),
        markets=_parse_json_field(prefs.markets),
        deal_size_min=prefs.deal_size_min,
        deal_size_max=prefs.deal_size_max,
        key_tenants=_parse_json_field(prefs.key_tenants),
        analysis_priorities=_parse_json_field(prefs.analysis_priorities),
        custom_notes=prefs.custom_notes,
        is_complete=prefs.is_complete,
        completion_percentage=completion,
        created_at=prefs.created_at,
        updated_at=prefs.updated_at,
    )


def build_personalized_context(prefs: UserPreferences) -> str:
    """
    Build a personalized context string for the system prompt.

    This is called by the orchestrator to inject user-specific context.
    """
    if not prefs:
        return ""

    lines = []

    # Role context
    role_descriptions = {
        "broker": "a commercial real estate broker representing tenants and landlords",
        "landlord": "a property owner managing commercial real estate assets",
        "investor": "a commercial real estate investor evaluating acquisition opportunities",
        "developer": "a developer creating new commercial properties",
        "analyst": "a market analyst researching commercial real estate trends",
    }

    if prefs.role:
        role_desc = role_descriptions.get(prefs.role, prefs.role)
        lines.append(f"You are assisting {role_desc}.")

    # Property focus
    property_types = _parse_json_field(prefs.property_types)
    if property_types:
        formatted = ", ".join(t.replace("_", " ").title() for t in property_types)
        lines.append(f"They focus on {formatted} properties.")

    # Tenant focus
    tenant_categories = _parse_json_field(prefs.tenant_categories)
    if tenant_categories:
        category_labels = {
            "qsr": "Quick Service Restaurants (QSR)",
            "casual_dining": "Casual Dining",
            "fast_casual": "Fast Casual",
            "fitness": "Fitness & Gyms",
            "medical": "Medical/Healthcare",
            "apparel": "Apparel & Fashion",
            "grocery": "Grocery",
            "convenience": "Convenience/Gas",
            "banking": "Banking & Financial",
            "beauty": "Beauty & Personal Care",
            "entertainment": "Entertainment",
            "discount": "Discount Retail",
            "auto": "Auto Services",
            "pet": "Pet Services",
            "coffee": "Coffee & Beverage",
        }
        formatted = ", ".join(category_labels.get(c, c.title()) for c in tenant_categories)
        lines.append(f"Their primary tenant focus areas: {formatted}.")

    # Geographic markets
    markets = _parse_json_field(prefs.markets)
    if markets:
        lines.append(f"They operate in: {', '.join(markets)}.")

    # Deal size
    if prefs.deal_size_min or prefs.deal_size_max:
        if prefs.deal_size_min and prefs.deal_size_max:
            lines.append(f"Typical deal size: {prefs.deal_size_min:,} - {prefs.deal_size_max:,} SF.")
        elif prefs.deal_size_min:
            lines.append(f"Minimum deal size: {prefs.deal_size_min:,} SF.")
        elif prefs.deal_size_max:
            lines.append(f"Maximum deal size: {prefs.deal_size_max:,} SF.")

    # Key tenants
    key_tenants = _parse_json_field(prefs.key_tenants)
    if key_tenants:
        lines.append(f"Key tenant relationships: {', '.join(key_tenants)}.")

    # Analysis priorities
    priorities = _parse_json_field(prefs.analysis_priorities)
    if priorities:
        priority_labels = {
            "traffic_counts": "traffic counts",
            "demographics": "demographic analysis",
            "void_analysis": "void/gap analysis",
            "competition": "competitive analysis",
            "visibility": "visibility and access",
            "co_tenancy": "co-tenancy opportunities",
        }
        formatted = ", ".join(priority_labels.get(p, p) for p in priorities)
        lines.append(f"Prioritize: {formatted}.")

    # Custom notes
    if prefs.custom_notes:
        lines.append(f"Additional context: {prefs.custom_notes}")

    if not lines:
        return ""

    return "\n\n**User Context:**\n" + "\n".join(lines)
