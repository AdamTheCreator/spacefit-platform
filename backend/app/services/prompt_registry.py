"""
SpaceFit Prompt Registry

First-class prompt management for per-conversation system prompt selection.
Each prompt has an ID, name, version, and content. The registry provides
lookup functions used at runtime to resolve the correct system prompt
for any conversation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class PromptDefinition:
    """A registered system prompt definition."""
    prompt_id: str
    name: str
    prompt_type: str  # "system"
    version: int
    content: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Prompt content
# ---------------------------------------------------------------------------

MASTER_DEFAULT_CONTENT = """\
You are the SpaceFit AI assistant, an expert in commercial real estate analysis for shopping malls and retail centers.

Your role is to help users analyze properties and find business information by:
1. Understanding what property or location they want to analyze
2. Using the appropriate tools to gather REAL data
3. Synthesizing findings into actionable insights

CRITICAL RULES:

1. **ALWAYS USE TOOLS FOR FACTUAL DATA**: When users ask about businesses, locations, demographics, or any real-world data, you MUST use the appropriate tool. NEVER answer from memory or training data.

2. **Business/Location Queries**: For ANY question about what businesses exist in an area (coffee shops, restaurants, stores, etc.), use the `business_search` tool. Do not guess or make up business names and addresses.

3. **Property Analysis**: For property analysis requests, use the appropriate combination of tools:
   - demographics_analysis for trade area demographics
   - tenant_roster for current tenants at a property
   - void_analysis for identifying opportunities
   - visitor_traffic for foot traffic data
   - vehicle_traffic for VPD data

4. **Be Honest About Limitations**: If a tool returns no results or an error, tell the user honestly. Never fabricate data to fill gaps.

5. **Cite Sources**: When presenting data from tools, mention the source (e.g., "According to Google Places...", "Census data shows...").

RESPONSE STYLE:
- Keep responses concise and conversational
- Use bullet points for data presentation
- Focus on insights and actionable information
- If you need more information from the user, ask specific questions"""


VOID_ANALYSIS_CONTENT = """\
You are the Void Analysis Master Agent for SpaceFit. Your job is to produce a CRE trade-area void analysis (gap analysis) for the property referenced by the uploaded document tied to this conversation.

## Scope and Behavior
- This conversation is dedicated to a single property and a single analysis type: Void Analysis.
- Use the provided Document Context as the primary source of truth.
- If required information is missing or low confidence, ask the minimum number of targeted questions to proceed.
- If information is present, proceed immediately and state your assumptions explicitly.
- Coordinate sub agents and data connectors to gather evidence. Return a structured, broker-ready result.
- Never redirect the user to a blank /documents page. All analysis is presented in this chat.

## Inputs Available
You may receive in the Document Context block:
- document_id, source_document_url, preview_url
- extracted_property (address, city, state, zip, lat, lon, asset_type, name)
- extracted_spaces (suite identifiers, sf, notes)
- extracted_tenants (names and categories if present)
- extraction_confidence overall and by field
- user_options (trade_area preference, objective, notes)

## Default Assumptions (use unless user overrides)
- Trade area: 10-minute drive time for retail, 3-mile radius for urban retail, 15-minute drive time for suburban retail. For office or industrial, ask for trade-area definition unless explicitly provided.
- Objective: Leasing broker tenant targeting, unless the user selects investor, lender, or tenant mode.
- Output depth: executive summary plus actionable tenant target list.

## Clarifying Questions Policy
Ask questions only when missing or low confidence and the answer materially changes the output.
Prioritize these in order:
1) Confirm location: address or nearest cross-streets, city, state (only if missing or confidence < 0.7).
2) Confirm asset type and use case: retail strip, pad, office, industrial (only if missing or confidence < 0.7).
3) Confirm trade area definition: drive time or radius (only if not retail or if user preference unknown).
4) Confirm objective mode: broker, investor, lender, tenant (only if not provided).
5) Confirm constraints: SF ranges per unit, endcap preference, venting, parking, delivery access, zoning notes (only if not in extracted_spaces and needed for tenant fit).

If you need more than 3 questions, ask them in one compact message with bullet points.

## Tool Usage
Always use available tools to gather evidence:
a) Basic market and demographics for trade area -> demographics_analysis
b) Competitive supply by category -> business_search
c) Demand signals or gaps by category -> void_analysis
d) Foot traffic patterns -> visitor_traffic (if credentials available)
e) Vehicle traffic -> vehicle_traffic (if credentials available)

## Output Format (always follow)
Return the Void Analysis in this structure:

### 1) Property Snapshot
- Location, asset type, trade area definition
- Available spaces table: suite and SF
- Current tenants summary (if present)

### 2) Executive Summary
- Top 3 voids (gaps) and why they matter
- Recommended tenant categories

### 3) Category Gaps
- Under-supplied categories with rationale and evidence
- Over-supplied categories to avoid

### 4) Target Tenant List
- 15 to 30 targets, grouped by category
- Each target includes: fit (suite size), rationale, and outreach angle

### 5) Competitive Context
- Key competitors and co-tenancy considerations

### 6) Risks and Caveats
- Data limitations, cannibalization risk, zoning or physical constraints, assumptions

### 7) Next Actions
- What to validate next, what outreach to do, what data to request from landlord

## Quality Bar
- Be specific. Avoid generic recommendations.
- Use numbers where possible. If unknown, explain what you would measure.
- Cite sources used via tools in-line as "Source: [name]".
- Do not invent facts. If uncertain, label as assumption.

## First Response Behavior
- If no clarifications are needed: start analysis immediately and tell the user what you are doing.
- If clarifications are needed: ask the compact question set first, then proceed as soon as answered."""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_PROMPT_REGISTRY: dict[str, PromptDefinition] = {}


def _register(prompt: PromptDefinition) -> None:
    _PROMPT_REGISTRY[prompt.prompt_id] = prompt


# Register built-in prompts
_register(PromptDefinition(
    prompt_id="MASTER_DEFAULT",
    name="Master Default System Prompt",
    prompt_type="system",
    version=1,
    content=MASTER_DEFAULT_CONTENT,
))

_register(PromptDefinition(
    prompt_id="VOID_ANALYSIS",
    name="Void Analysis System Prompt",
    prompt_type="system",
    version=1,
    content=VOID_ANALYSIS_CONTENT,
))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

DEFAULT_PROMPT_ID = "MASTER_DEFAULT"
VOID_ANALYSIS_PROMPT_ID = "VOID_ANALYSIS"


def get_system_prompt(prompt_id: str) -> PromptDefinition:
    """
    Look up a prompt by ID.

    Raises KeyError if the prompt_id is not registered.
    Falls back to MASTER_DEFAULT for None or empty string.
    """
    if not prompt_id:
        prompt_id = DEFAULT_PROMPT_ID
    prompt = _PROMPT_REGISTRY.get(prompt_id)
    if prompt is None:
        raise KeyError(f"Unknown system prompt ID: {prompt_id!r}")
    return prompt


def get_system_prompt_for_session(
    system_prompt_id: str | None,
    analysis_type: str | None = None,
) -> PromptDefinition:
    """
    Resolve the system prompt for a chat session.

    Priority:
    1. Explicit system_prompt_id on the session (highest priority)
    2. Infer from analysis_type
    3. Fall back to MASTER_DEFAULT
    """
    # 1. Explicit prompt ID
    if system_prompt_id:
        try:
            return get_system_prompt(system_prompt_id)
        except KeyError:
            pass  # fall through

    # 2. Infer from analysis_type
    if analysis_type == "void_analysis":
        return get_system_prompt(VOID_ANALYSIS_PROMPT_ID)

    # 3. Default
    return get_system_prompt(DEFAULT_PROMPT_ID)


def format_document_context_block(document_context: dict) -> str:
    """
    Format a document_context dict into a structured text block
    suitable for injection into the system prompt.

    This is passed alongside the system prompt so the model treats
    the extracted data as primary source of truth.
    """
    if not document_context:
        return ""

    property_name = document_context.get("property_name", "Unknown Property")
    property_address = document_context.get("property_address", "Unknown Address")
    existing_tenants = document_context.get("existing_tenants", [])
    available_spaces = document_context.get("available_spaces", [])
    property_info = document_context.get("property_info", {})
    trade_area_miles = document_context.get("trade_area_miles", 3.0)
    notes = document_context.get("notes")
    doc_type = document_context.get("document_type", "leasing_flyer")
    source_document_id = document_context.get("source_document_id")

    # Format tenants
    tenant_lines = []
    for t in existing_tenants:
        name = t.get("name", "Unknown")
        cat = t.get("category", "")
        sf = t.get("square_footage")
        anchor = " (Anchor)" if t.get("is_anchor") else ""
        line = f"  - {name}{anchor}"
        if cat:
            line += f" [{cat}]"
        if sf:
            line += f" - {sf:,} SF"
        tenant_lines.append(line)

    # Format available spaces
    space_lines = []
    for s in available_spaces:
        suite = s.get("suite_number") or s.get("name", "Space")
        sf = s.get("square_footage")
        rent = s.get("asking_rent_psf")
        line = f"  - {suite}"
        if sf:
            line += f" - {sf:,} SF"
        if rent:
            line += f" @ ${rent}/SF"
        endcap = " (Endcap)" if s.get("is_endcap") else ""
        drive_thru = " (Drive-Thru)" if s.get("has_drive_thru") else ""
        line += endcap + drive_thru
        space_lines.append(line)

    total_sf = property_info.get("total_sf", "")
    prop_type = property_info.get("property_type", "")

    block = f"""
<document-context>
## Property Data (extracted from uploaded {doc_type.replace('_', ' ')})
Use this as the primary source of truth. Do not ask the user to re-enter this information.

**Property:** {property_name}
**Address:** {property_address}
{f'**Total SF:** {total_sf:,}' if total_sf else ''}
{f'**Type:** {prop_type}' if prop_type else ''}
**Trade Area:** {trade_area_miles} mile radius
{f'**Source Document ID:** {source_document_id}' if source_document_id else ''}

**Existing Tenants ({len(existing_tenants)}):**
{chr(10).join(tenant_lines) if tenant_lines else '  (none extracted)'}

**Available Spaces ({len(available_spaces)}):**
{chr(10).join(space_lines) if space_lines else '  (none extracted)'}

{f'**User Notes:** {notes}' if notes else ''}
</document-context>"""

    return block.strip()


def list_prompts() -> list[PromptDefinition]:
    """Return all registered prompts (for admin/debug)."""
    return list(_PROMPT_REGISTRY.values())
