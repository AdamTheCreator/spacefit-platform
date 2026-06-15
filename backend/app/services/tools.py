"""
Space Goose AI Tools Definition

Defines all available tools for Claude's native tool calling.
This replaces the keyword-matching approach with structured tool use.
"""

from typing import Any

# Tool definitions following Anthropic's tool_use schema
SPACEGOOSE_TOOLS: list[dict[str, Any]] = [
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
                    "description": "Concrete street address, city, or neighborhood to search around (e.g., '2425 S 6th Ave, Tucson, AZ' or 'downtown Fairfield'). If the current session is scoped to a project, default to that project's property address unless the user explicitly names a different place. Do NOT pass vague placeholders like 'the location' or 'this property' — if no concrete address is available from the user or project context, ask the user for one instead of calling the tool."
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
                    "description": "Concrete street address to analyze demographics for. If the session is scoped to a project, default to the project's property address unless the user names another place. Do NOT pass vague placeholders like 'the property' — ask the user for an address instead of calling the tool without one."
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
                    "description": "Concrete street address of the shopping center or commercial property. If the session is scoped to a project, default to that project's property address unless the user names another place. Do NOT pass vague placeholders — ask the user for an address instead."
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
                    "description": "Concrete street address of the property to analyze. If the session is scoped to a project, default to that project's property address unless the user names another place. Do NOT pass vague placeholders — ask the user for an address instead."
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
    {
        "name": "foot_traffic",
        "description": """Get live foot-traffic metrics for a commercial property from Placer.ai mobile-location data.

USE THIS TOOL WHEN:
- User asks how busy a location is, its foot traffic, or visitor volume
- User asks about vehicles per day (VPD), peak days/hours, or dwell time
- User wants to gauge how a retail site performs (actual visitors, not just residents)
- User asks about the year-over-year traffic trend for a property

Returns ACTUAL visitor counts from mobile data — distinct from demographics_analysis (who lives nearby). Requires a concrete street address; if the session is scoped to a project, default to that project's property address unless the user names another place. Do NOT pass vague placeholders like 'this property' — ask the user for an address instead.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "Concrete street address of the commercial property or shopping center (e.g., '2425 S 6th Ave, Tucson, AZ'). If the session is scoped to a project, default to the project's property address unless the user names another place."
                }
            },
            "required": ["address"]
        }
    },
    {
        "name": "costar_import",
        "description": """Parse a user-uploaded CoStar CSV export (lease comps, tenant roster, or property lookup) into structured property + tenant data.

USE THIS TOOL WHEN:
- User asks about their CoStar data or uploaded CoStar CSV
- User references lease comps, tenant rosters, or property data they've imported
- User says they've uploaded a CoStar file""",
        "input_schema": {
            "type": "object",
            "properties": {
                "import_job_id": {
                    "type": "string",
                    "description": "ID of the user's uploaded CoStar CSV import job"
                },
            },
            "required": ["import_job_id"],
        },
    },
    {
        "name": "placer_import",
        "description": """Parse a user-uploaded Placer.ai property report PDF into trade area metrics (visits, demographics, home ZIPs).

USE THIS TOOL WHEN:
- User asks about their Placer data or uploaded Placer report
- User references foot traffic, visitor demographics, or trade area data they've imported
- User says they've uploaded a Placer file""",
        "input_schema": {
            "type": "object",
            "properties": {
                "import_job_id": {
                    "type": "string",
                    "description": "ID of the user's uploaded Placer PDF import job"
                },
            },
            "required": ["import_job_id"],
        },
    },
    {
        "name": "siteusa_import",
        "description": """Parse a user-uploaded SiteUSA CSV export into vehicle traffic and demographics data.

USE THIS TOOL WHEN:
- User asks about their SiteUSA data or uploaded SiteUSA CSV
- User references vehicle traffic counts (VPD) they've imported
- User says they've uploaded a SiteUSA file""",
        "input_schema": {
            "type": "object",
            "properties": {
                "import_job_id": {
                    "type": "string",
                    "description": "ID of the user's uploaded SiteUSA CSV import job"
                },
            },
            "required": ["import_job_id"],
        },
    },
    {
        "name": "document_search",
        "description": """Search the text of documents attached to the current project for content matching a natural-language query. Returns the top matching snippets with filename and page number so you can quote them with a citation.

USE THIS TOOL WHEN:
- The user asks about content inside a project document that isn't in the summary block (e.g., "what does the OM say about the loan covenant", "find any mention of CAM charges", "what's the parking ratio in the site plan")
- The user asks to find or quote specific language from an attached document
- You need to verify or cite a claim before answering

DO NOT use this tool when the session is not scoped to a project — it will return no results.
Always include the document filename and page number from the result when you cite a snippet (e.g., "per Greenway-OM.pdf p.4, …").""",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural-language search query. Use the user's words; the index does keyword matching with English stemming."
                },
                "project_id": {
                    "type": "string",
                    "description": "Project to search within. Use the project_id from the project-context block in the system prompt; without it the tool returns no results."
                },
                "document_id": {
                    "type": "string",
                    "description": "Optional: restrict the search to a single document by id. Omit to search across all of the project's completed documents."
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum snippets to return (default 5, hard cap 15).",
                    "default": 5
                }
            },
            "required": ["query", "project_id"]
        }
    },
    {
        "name": "draft_outreach",
        "description": """Draft personalized outreach emails to a list of target tenants for a specific property vacancy. Returns drafts for user review — does NOT send.

USE THIS TOOL WHEN:
- User asks to draft outreach, emails, or reach out to tenants
- User wants to contact tenants about a vacancy
- User says "draft emails" or "create outreach" for a property""",
        "input_schema": {
            "type": "object",
            "properties": {
                "property_address": {
                    "type": "string",
                    "description": "Address of the property with the vacancy"
                },
                "vacancy_description": {
                    "type": "string",
                    "description": "Suite/SF/use type of the vacancy (e.g. '4,200 SF endcap with drive-thru')"
                },
                "target_tenants": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "contact_email": {"type": "string"},
                            "rationale": {
                                "type": "string",
                                "description": "Why this tenant is a fit"
                            },
                        },
                        "required": ["name"],
                    },
                },
            },
            "required": ["property_address", "target_tenants"],
        },
    },
]


def get_tools_for_context(
    has_imported_data: dict[str, bool] | None = None,
) -> list[dict[str, Any]]:
    """
    Get the list of tools available based on user's imported data.

    Phase 2 will add import-gated tools (costar_import, placer_import, draft_outreach).
    For now, all remaining tools are always available.
    """
    return list(SPACEGOOSE_TOOLS)


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
