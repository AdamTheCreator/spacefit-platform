"""
SpaceFit AI Tools Definition

Defines all available tools for Claude's native tool calling.
This replaces the keyword-matching approach with structured tool use.
"""

from typing import Any

# Tool definitions following Anthropic's tool_use schema
SPACEFIT_TOOLS: list[dict[str, Any]] = [
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
                    "description": "Trade area radius in miles (default: 5)",
                    "default": 5
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
                "radius_meters": {
                    "type": "integer",
                    "description": "Search radius in meters (default: 500 for focused property search)",
                    "default": 500
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
                }
            },
            "required": ["address"]
        }
    },
    {
        "name": "visitor_traffic",
        "description": """Get foot traffic and visitor data for a location (requires Placer.ai credentials).

USE THIS TOOL WHEN:
- User asks about foot traffic or visitor counts
- User wants to know how many people visit a location
- User asks about peak hours or busy times
- User wants visitor demographics (age, gender, income of visitors)""",
        "input_schema": {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "Address of the location to analyze"
                }
            },
            "required": ["address"]
        }
    },
    {
        "name": "vehicle_traffic",
        "description": """Get vehicle traffic counts (VPD - Vehicles Per Day) for a location (requires SiteUSA credentials).

USE THIS TOOL WHEN:
- User asks about traffic counts or VPD
- User wants to know vehicle traffic on nearby roads
- User asks about accessibility or drive-by traffic""",
        "input_schema": {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "Address of the location to analyze"
                }
            },
            "required": ["address"]
        }
    },
]


def get_tools_for_context(
    has_placer_credentials: bool = False,
    has_siteusa_credentials: bool = False,
    has_costar_credentials: bool = False,
) -> list[dict[str, Any]]:
    """
    Get the list of tools available based on user's credentials.

    Some tools require premium data source credentials to function.
    This allows us to only show tools the user can actually use.
    """
    available_tools = []

    for tool in SPACEFIT_TOOLS:
        tool_name = tool["name"]

        # These tools are always available (use free APIs)
        if tool_name in ("business_search", "demographics_analysis", "tenant_roster", "void_analysis"):
            available_tools.append(tool)

        # Visitor traffic requires Placer.ai
        elif tool_name == "visitor_traffic" and has_placer_credentials:
            available_tools.append(tool)

        # Vehicle traffic requires SiteUSA
        elif tool_name == "vehicle_traffic" and has_siteusa_credentials:
            available_tools.append(tool)

    return available_tools


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
