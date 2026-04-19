"""
Perigee AI Tools Definition

Defines all available tools for Claude's native tool calling.
This replaces the keyword-matching approach with structured tool use.
"""

from typing import Any

# Tool definitions following Anthropic's tool_use schema
PERIGEE_TOOLS: list[dict[str, Any]] = [
    {
        "name": "business_search",
        "description": """Search for businesses by type and location using real-time data from Google Places.

USE THIS TOOL WHEN:
- User asks about businesses in a specific location (e.g., "coffee shops in Westport, CT")
- User asks about restaurants, stores, cafes, or any commercial establishments
- User wants to know what businesses exist in an area
- User asks "what's near" or "businesses around" a location

DO NOT answer questions about local businesses from memory - ALWAYS use this tool to get accurate, real-time data.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query combining business type and location (e.g., 'coffee shops Westport CT', 'restaurants downtown Fairfield')"
                },
                "business_type": {
                    "type": "string",
                    "description": "Type of business to search for (e.g., 'coffee shop', 'restaurant', 'gym', 'bank')"
                },
                "location": {
                    "type": "string",
                    "description": "City, town, address, or area to search in (e.g., 'Westport, CT', 'downtown Fairfield')"
                },
                "radius_miles": {
                    "type": "number",
                    "description": "Search radius in miles (default: 2)",
                    "default": 2
                }
            },
            "required": ["location"]
        }
    },
    {
        "name": "demographics_analysis",
        "description": """Analyze trade area demographics using Census ACS data.

USE THIS TOOL WHEN:
- User asks about population, income, age distribution in an area
- User wants demographic analysis for a property or location
- User asks about the "trade area" or "market" for a property
- Analysis requires understanding who lives/works near a location""",
        "input_schema": {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "Address or location to analyze demographics for"
                },
                "radius_miles": {
                    "type": "number",
                    "description": "Trade area radius in miles. Standard options: 1, 3, 5, or 10 miles. Default: 3.",
                    "default": 3
                }
            },
            "required": ["address"]
        }
    },
    {
        "name": "tenant_roster",
        "description": """Get the current tenant roster for a shopping center or commercial property.

USE THIS TOOL WHEN:
- User asks about tenants at a specific mall or shopping center
- User wants to know what stores are in a property
- User asks about the "tenant mix" of a property
- User provides a property address and wants to see current occupants""",
        "input_schema": {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "Address of the shopping center or commercial property"
                },
                "radius_miles": {
                    "type": "number",
                    "description": "Trade area radius in miles (default: 1.0 for focused property, use 3-5 for broader trade area)",
                    "default": 1.0
                }
            },
            "required": ["address"]
        }
    },
    {
        "name": "void_analysis",
        "description": """Identify missing tenant categories and opportunities for a property.

USE THIS TOOL WHEN:
- User asks about "voids" or "gaps" in a tenant mix
- User wants to know what's missing from a property
- User asks about opportunities for new tenants
- User wants recommendations for what businesses would do well at a location

NOTE: This tool works best when demographics and tenant data have already been gathered.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "Address of the property to analyze"
                },
                "radius_miles": {
                    "type": "number",
                    "description": "Trade area radius in miles (default: 3.0)",
                    "default": 3.0
                }
            },
            "required": ["address"]
        }
    },
    # TODO: costar_import, placer_import, draft_outreach tools will be added in Phase 2
]


def get_tools_for_context(
    has_imported_data: dict[str, bool] | None = None,
) -> list[dict[str, Any]]:
    """
    Get the list of tools available based on user's imported data.

    Phase 2 will add import-gated tools (costar_import, placer_import, draft_outreach).
    For now, all remaining tools are always available.
    """
    return list(PERIGEE_TOOLS)


# Query classification to determine if tools should be forced
FACTUAL_QUERY_PATTERNS = [
    # Business/location queries - MUST use tools
    "coffee", "restaurant", "store", "shop", "business", "cafe", "bar",
    "gym", "bank", "salon", "spa", "hotel", "gas station",
    "what's near", "what is near", "businesses in", "businesses at",
    "places in", "places near", "located in", "located at",
    # Property analysis queries
    "tenant", "void", "demographic", "traffic", "population", "income",
    "trade area", "market analysis",
    # CoStar-specific queries
    "costar", "lease expiration", "rent psf", "property owner", "sale history",
]


def should_force_tool_use(user_message: str) -> bool:
    """
    Determine if the user's query requires factual data retrieval.

    If True, we should use tool_choice="any" to force Claude to use a tool
    rather than answering from training data (which could hallucinate).
    """
    message_lower = user_message.lower()

    # Check for factual query patterns
    for pattern in FACTUAL_QUERY_PATTERNS:
        if pattern in message_lower:
            return True

    # Check for location + question pattern
    location_indicators = ["in ", "at ", "near ", "around ", "downtown "]
    question_indicators = ["what", "where", "how many", "list", "show me", "find"]

    has_location = any(loc in message_lower for loc in location_indicators)
    has_question = any(q in message_lower for q in question_indicators)

    if has_location and has_question:
        return True

    return False
